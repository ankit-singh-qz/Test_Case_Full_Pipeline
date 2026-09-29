"""Thin LLM wrapper -- deliberately duplicated from fdd_pipeline/llm.py,
tdd_pipeline/llm.py, and test_design_pipeline/llm.py rather than shared,
so this pipeline has no import dependency on any of them (fully
decoupled: separate process, separate failure domain). Provider
settings come from the shared .env one folder up.

This file is a copy of test_design_pipeline/llm.py. It had previously
drifted a full generation behind it -- no transient-error classification,
no jitter, no streaming, no runaway guard, no per-agent max_tokens -- even
though this pipeline is the MORE exposed of the two: it fans out ten
agents at once and expand_test_cases can turn each into two calls. It also
read response.content as a string, which raises AttributeError whenever
ChatBedrockConverse hands back a list of content blocks.
"""
import json
import os
import random
import threading
import time
import zlib
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_llm = None
_llm_lock = threading.Lock()

# Tier 1 fans all ten technique agents out at once, and each can make a
# second call from expand_test_cases. Bedrock answers a burst like that
# with ServiceUnavailableException far more readily than it answers the
# same calls spread out, and because the whole tier then retries in step,
# the burst repeats. Gate concurrent calls so the fan-out becomes a queue.
# 4 keeps most of the wall-clock win of parallelism; drop it to 1 to
# serialize completely while a region is struggling.
MAX_CONCURRENCY = max(1, int(os.getenv("LLM_MAX_CONCURRENCY", "15")))
_call_slots = threading.Semaphore(MAX_CONCURRENCY)

# One bad network blip (a Bedrock read timeout, or Bedrock briefly
# rejecting calls with ServiceUnavailableException) or one malformed
# generation (a model that keeps writing after a valid JSON object
# closes) used to kill an entire multi-agent run outright, with no
# second chance. Retry a few times with backoff before giving up.
# ServiceUnavailable is different from a read timeout: botocore's own
# retries return almost immediately, so a short 5s/10s app-level backoff
# still dies while Bedrock is rejecting traffic. Give that case more
# attempts and a longer wait -- and jitter it, because a whole tier
# retrying on the identical schedule just reproduces the burst that
# failed.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5
TRANSIENT_ATTEMPTS = 6
TRANSIENT_BACKOFF_SECONDS = 15
MAX_BACKOFF_SECONDS = 120

# After this many transient failures in a row, the region or the model is
# not coming back inside one retry budget -- switch to the fallback if one
# is configured rather than spending the rest of the attempts on it.
FAILURES_BEFORE_FALLBACK = 3

# --- Runaway-generation guard -------------------------------------------
# Bedrock's non-streaming `converse` call sends NOTHING until the model has
# finished the whole reply, so botocore's read timeout is really a timeout on
# total generation time. A model that falls into a repetition loop (typically
# while writing out a long literal string such as a 50-char boundary value)
# keeps generating until it hits max_tokens, the socket sits silent, and the
# call dies with ReadTimeoutError -- with no partial output to diagnose from.
# Streaming turns that silent wait into observable chunks: the read timeout
# then only fires on a genuine stall, and a loop can be detected and aborted
# after a few hundred characters instead of after 120+ seconds.
READ_TIMEOUT_SECONDS = int(os.getenv("LLM_READ_TIMEOUT", "120"))
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "24000"))
RUNAWAY_TAIL_CHARS = 800          # window inspected for repetition
RUNAWAY_MAX_COMPRESSION = 0.08    # real JSON output: >=0.17; loops: <=0.03
RUNAWAY_RETRY_TEMPERATURE = 0.4   # temperature=0 replays the same loop
MAX_RUNAWAY_RETRIES = 2


class RunawayGenerationError(Exception):
    """The model degenerated into repetition (or exceeded max_chars)."""

    def __init__(self, message: str, tail: str = ""):
        super().__init__(message)
        self.tail = tail


_TRANSIENT_ERROR_NAMES = {
    "ServiceUnavailableException",
    "ThrottlingException",
    "TooManyRequestsException",
    "ReadTimeoutError",
    "ConnectTimeoutError",
    "EndpointConnectionError",
    "ConnectionClosedError",
    "ResponseStreamingError",
}


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return (
        name in _TRANSIENT_ERROR_NAMES
        or "serviceunavailable" in text
        or "throttl" in text
        or "unable to process your request" in text
        or "read timed out" in text
        or "read timeout" in text
    )


def _warn_on_misnamed_bedrock_key() -> None:
    """langchain-aws reads AWS_BEARER_TOKEN_BEDROCK. A .env that sets the
    shorter AWS_BEARER_TOKEN looks right and does nothing -- boto3 falls
    through to the ordinary credential chain, so the run either picks up
    unrelated credentials or fails with an auth error far from the cause."""
    if os.getenv("AWS_BEARER_TOKEN") and not os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
        print(
            "WARNING: AWS_BEARER_TOKEN is set but AWS_BEARER_TOKEN_BEDROCK is "
            "not. langchain-aws only reads the latter, so this token is being "
            "ignored and boto3 is using the default credential chain.",
            flush=True,
        )


def _bedrock_client_config():
    """botocore settings the LangChain constructor does not expose.

    - adaptive retry mode adds client-side rate limiting: botocore itself
      slows down after a throttle instead of firing the next call
      immediately. max_retries=0 (what this used to pass) turned that off
      entirely and left our loop as the only backoff.
    - max_pool_connections defaults to 10, which is exactly the size of
      the technique tier. Raise it so a queued call is never also waiting
      on a socket.
    """
    from botocore.config import Config

    return Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        max_pool_connections=max(16, MAX_CONCURRENCY * 4),
        read_timeout=READ_TIMEOUT_SECONDS,
        connect_timeout=10,
    )


def _bedrock_llm(model_id: str, region_name: str):
    from langchain_aws import ChatBedrockConverse

    _warn_on_misnamed_bedrock_key()
    return ChatBedrockConverse(
        model_id=model_id,
        region_name=region_name,
        temperature=0,
        # timeout applies to connect AND read. Because call_agent
        # streams, "read" means "no bytes for this long" (a real stall),
        # not "total generation time".
        timeout=READ_TIMEOUT_SECONDS,
        config=_bedrock_client_config(),
        # Hard backstop against runaway output. Per-agent limits are
        # applied through call_agent(max_tokens=...).
        max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )


def get_fallback_llm():
    """A second Bedrock client on a different model or region, used only
    after FAILURES_BEFORE_FALLBACK consecutive transient errors. Returns
    None when neither BEDROCK_FALLBACK_MODEL_ID nor AWS_FALLBACK_REGION is
    set, or when the fallback would be identical to the primary."""
    if os.getenv("LLM_PROVIDER", "anthropic").lower() != "bedrock":
        return None

    primary_model = os.getenv(
        "BEDROCK_MODEL_ID",
        os.getenv("BEDROCK_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
    )
    primary_region = os.getenv("AWS_REGION", "eu-north-1")
    model_id = os.getenv("BEDROCK_FALLBACK_MODEL_ID", primary_model)
    region_name = os.getenv("AWS_FALLBACK_REGION", primary_region)
    if (model_id, region_name) == (primary_model, primary_region):
        return None
    return _bedrock_llm(model_id, region_name)


def get_llm():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            temperature=0,
            timeout=180,
            max_retries=2,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0,
            timeout=180,
            max_retries=2,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
            temperature=0,
        )
    if provider == "bedrock":
        return _bedrock_llm(
            os.getenv(
                "BEDROCK_MODEL_ID",
                os.getenv("BEDROCK_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
            ),
            os.getenv("AWS_REGION", "eu-north-1"),
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _extract_first_json_object(text: str) -> str:
    """Some models occasionally keep writing after a valid JSON object
    closes (self-check commentary, a duplicate/corrected attempt, etc.),
    which makes a plain json.loads fail with "Extra data" even though a
    perfectly valid object is sitting right there at the start. Scan for
    the first balanced {...} block -- tracking quoted strings so braces
    inside string values don't throw off the depth count -- and return
    just that slice instead of the whole response."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response.")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError("No balanced JSON object found in response.")


def _parse_json_response(raw: str) -> dict:
    """Try a strict parse first (the common case); if the model appended
    anything after a valid object, fall back to extracting just the first
    balanced {...} block instead of giving up outright."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_extract_first_json_object(raw))


def _content_to_text(content) -> str:
    """Message/chunk content is a str for most providers but can be a list
    of content blocks (dicts with a "text" key) on newer integrations."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type", "text") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _is_degenerate(tail: str) -> bool:
    """True when the last RUNAWAY_TAIL_CHARS of output are almost pure
    repetition ('1234567890' * n, 'AAAA...'), judged by how well they
    compress. Ordinary pretty-printed JSON never gets near the threshold."""
    if len(tail) < RUNAWAY_TAIL_CHARS:
        return False
    raw = tail.encode("utf-8")
    return len(zlib.compress(raw)) / len(raw) < RUNAWAY_MAX_COMPRESSION


def _backoff_seconds(base: int, attempt: int) -> float:
    """Full jitter, per AWS's own guidance: a uniform draw from
    [0, base * 2^(attempt-1)], capped.

    The old `base * attempt` was deterministic, so every thread in a tier
    slept the identical 15s, then 30s, then 45s and hit Bedrock together
    each time. Whatever made the first burst fail was therefore guaranteed
    to see the same burst again. Spreading the retries is most of the
    difference between recovering and exhausting the budget."""
    ceiling = min(base * (2 ** max(0, attempt - 1)), MAX_BACKOFF_SECONDS)
    return random.uniform(0, ceiling)


def _stream_completion(llm, messages, max_chars: int) -> str:
    """Consume llm.stream(), aborting early on repetition or overlong output.
    Returns the full text. Raises RunawayGenerationError on a loop.

    Held under _call_slots so at most MAX_CONCURRENCY calls are in flight
    across every thread in the process."""
    parts: list[str] = []
    total = 0
    tail = ""
    next_check = RUNAWAY_TAIL_CHARS
    with _call_slots:
        for chunk in llm.stream(messages):
            text = _content_to_text(chunk.content)
            if not text:
                continue
            parts.append(text)
            total += len(text)
            tail = (tail + text)[-RUNAWAY_TAIL_CHARS:]
            if total >= next_check:
                next_check = total + 200
                if _is_degenerate(tail):
                    raise RunawayGenerationError(
                        f"Repetition loop detected after {total} chars.", tail
                    )
            if total > max_chars:
                raise RunawayGenerationError(
                    f"Output exceeded {max_chars} chars without finishing.", tail
                )
    return "".join(parts)


def _bind_limits(llm, max_tokens=None, temperature=None):
    """Per-call overrides. Only wired for Bedrock (the provider this
    pipeline runs on); other providers keep their constructor settings."""
    if os.getenv("LLM_PROVIDER", "anthropic").lower() != "bedrock":
        return llm
    kwargs = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    return llm.bind(**kwargs) if kwargs else llm


RUNAWAY_GUIDANCE = (
    "\n\nIMPORTANT: a previous attempt degenerated into a repetition loop "
    "while writing a long literal string. Never write out any string longer "
    "than 16 characters. Describe long values symbolically instead, e.g. "
    "<string of 50 chars>, and keep the whole reply compact."
)


def call_agent(
    system_prompt: str, payload: dict, max_tokens: int | None = None
) -> dict:
    """Send a system prompt + JSON payload to the LLM and parse a strict-JSON
    reply. Retries a few times, with backoff, on transient network errors
    (e.g. Bedrock read timeouts) and on malformed JSON (e.g. trailing
    commentary after a valid object, or a code-like expression such as
    "A".repeat(50) used in place of a literal string value) before giving
    up. Raises ValueError with the raw output if every attempt still
    fails to parse.

    temperature=0 means a bare retry with the same messages tends to
    reproduce the exact same malformed output rather than self-correct --
    so on a JSON parse failure, the bad reply and the specific parse error
    are fed back to the model as part of the conversation before retrying,
    giving each retry attempt an actual chance to fix the mistake.

    The reply is streamed so a repetition loop is caught within a few hundred
    characters (RunawayGenerationError) instead of surfacing minutes later as
    a ReadTimeoutError. max_tokens is a per-agent output cap (None = the
    provider-level default set in get_llm)."""
    global _llm
    if _llm is None:
        # Several agent threads reach this at once on the first tier.
        with _llm_lock:
            if _llm is None:
                _llm = get_llm()

    base_prompt = json.dumps(payload, indent=2, default=str)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=base_prompt),
    ]
    # ~3 chars/token is a conservative floor for JSON; +25% slack.
    max_chars = int((max_tokens or DEFAULT_MAX_OUTPUT_TOKENS) * 3 * 1.25)
    runaway_failures = 0
    client = _llm
    llm = _bind_limits(client, max_tokens=max_tokens)

    last_raw = ""
    last_exc = None
    json_failures = 0
    transient_streak = 0
    on_fallback = False

    for attempt in range(1, TRANSIENT_ATTEMPTS + 1):
        try:
            print(f"LLM request (attempt {attempt})...", flush=True)
            reply_text = _stream_completion(llm, messages, max_chars)
        except RunawayGenerationError as exc:
            last_exc = exc
            runaway_failures += 1
            print(
                f"LLM runaway generation ({exc}) -- tail: {exc.tail[-80:]!r}",
                flush=True,
            )
            if runaway_failures > MAX_RUNAWAY_RETRIES or attempt >= TRANSIENT_ATTEMPTS:
                raise ValueError(
                    f"Model kept degenerating into repetition after "
                    f"{runaway_failures} attempts. Last tail:\n{exc.tail[-400:]}"
                ) from exc
            # temperature=0 would replay the identical loop: raise it a
            # little and tell the model what went wrong. The runaway reply
            # itself is NOT fed back (it is huge and pure noise).
            llm = _bind_limits(
                client, max_tokens=max_tokens, temperature=RUNAWAY_RETRY_TEMPERATURE
            )
            messages[1] = HumanMessage(content=base_prompt + RUNAWAY_GUIDANCE)
            continue
        except Exception as exc:  # network timeouts, throttling, Bedrock 503s
            last_exc = exc
            # A read timeout already burned the full client timeout.
            # Retrying that six times is what stretched one stalled call
            # past 10 minutes. Two tries is enough; immediate 503s still
            # get the longer transient budget.
            timed_out = type(exc).__name__ in {"ReadTimeoutError", "ConnectTimeoutError"} or "read timeout" in str(exc).lower()
            transient = _is_transient(exc)
            if timed_out:
                limit = 2
            elif transient:
                limit = TRANSIENT_ATTEMPTS
            else:
                limit = MAX_ATTEMPTS
            if attempt >= limit:
                raise

            transient_streak = transient_streak + 1 if transient else 0
            if transient_streak >= FAILURES_BEFORE_FALLBACK and not on_fallback:
                fallback = get_fallback_llm()
                if fallback is not None:
                    print(
                        f"{transient_streak} transient failures in a row; "
                        "switching to the fallback model/region.",
                        flush=True,
                    )
                    client = fallback
                    on_fallback = True
                    transient_streak = 0

            llm = _bind_limits(client, max_tokens=max_tokens)
            wait = _backoff_seconds(
                TRANSIENT_BACKOFF_SECONDS if transient else RETRY_BACKOFF_SECONDS,
                attempt,
            )
            print(
                f"LLM call failed ({type(exc).__name__}). "
                f"Retrying in {wait:.1f}s (attempt {attempt}/{limit}).",
                flush=True,
            )
            time.sleep(wait)
            continue

        transient_streak = 0
        raw = _strip_code_fence(reply_text)
        last_raw = raw
        try:
            parsed = _parse_json_response(raw)
            print("@@CASES_STEP", flush=True)
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            json_failures += 1
            if json_failures >= MAX_ATTEMPTS or attempt >= TRANSIENT_ATTEMPTS:
                raise ValueError(
                    f"Agent did not return valid JSON after {json_failures} attempts. "
                    f"Raw output (truncated):\n{last_raw[:2000]}"
                ) from exc
            # Feed the bad reply + the exact parse error back so the next
            # attempt sees what was wrong, instead of silently repeating
            # an identical request that will just reproduce the same bug.
            messages.append(AIMessage(content=reply_text))
            messages.append(
                HumanMessage(
                    content=(
                        "That response was not valid JSON: "
                        f"{exc}\n\n"
                        "Every value must be a literal JSON string, number, "
                        "boolean, array, or object -- never a code-like "
                        'expression (e.g. "A".repeat(50)). Never write out a '
                        "string longer than 16 characters. A length boundary "
                        'is a descriptor: "<string of 50 chars>". Return the '
                        "corrected, complete JSON object only -- no "
                        "commentary, no code fences."
                    )
                )
            )
            time.sleep(_backoff_seconds(RETRY_BACKOFF_SECONDS, attempt))

    # Unreachable in practice -- every branch above either returns or
    # raises -- but keeps this function's control flow explicit.
    raise last_exc or ValueError("call_agent failed with no captured error.")