"""Thin LLM wrapper -- deliberately duplicated from fdd_pipeline/llm.py
rather than shared, so this pipeline has no import dependency on
fdd_pipeline (fully decoupled: separate process, separate failure
domain). Provider settings come from the shared .env one folder up.
"""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_llm = None

# One bad network blip (a Bedrock read timeout) or one malformed generation
# (a model that keeps writing after a valid JSON object closes) used to
# kill the entire 16-agent run outright, with no second chance. Retry a
# few times with backoff before giving up -- both failure modes are common
# enough with a fast/cheap model to be worth the extra latency.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5


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
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                os.getenv("BEDROCK_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
            ),
            region_name=os.getenv("AWS_REGION", "eu-north-1"),
            temperature=0,
            # Bedrock's default 60s read timeout is too tight for the
            # heaviest agent (16, whose payload is every other section's
            # output) -- give it more room, and let botocore itself retry
            # a couple of times on top of our own retry loop in call_agent.
            timeout=180,
            max_retries=2,
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


def call_agent(system_prompt: str, payload: dict) -> dict:
    """Send a system prompt + JSON payload to the LLM and parse a strict-JSON
    reply. Retries a few times, with backoff, on transient network errors
    (e.g. Bedrock read timeouts) and on malformed JSON (e.g. trailing
    commentary after a valid object) before giving up. Raises ValueError
    with the raw output if every attempt still fails to parse."""
    global _llm
    if _llm is None:
        _llm = get_llm()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(payload, indent=2, default=str)),
    ]

    last_raw = ""
    last_exc = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = _llm.invoke(messages)
        except Exception as exc:  # network timeouts, throttling, etc.
            last_exc = exc
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

        raw = _strip_code_fence(response.content)
        last_raw = raw
        try:
            parsed = _parse_json_response(raw)
            print("@@TDD_STEP", flush=True)
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            if attempt == MAX_ATTEMPTS:
                raise ValueError(
                    f"Agent did not return valid JSON after {MAX_ATTEMPTS} attempts. "
                    f"Raw output (truncated):\n{last_raw[:2000]}"
                ) from exc
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    # Unreachable in practice -- every branch above either returns or
    # raises -- but keeps this function's control flow explicit.
    raise last_exc or ValueError("call_agent failed with no captured error.")
