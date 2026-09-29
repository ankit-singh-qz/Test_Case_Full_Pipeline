"""Thin LLM wrapper. Supports Anthropic, OpenAI, Gemini, or AWS Bedrock via
env var LLM_PROVIDER. Every agent calls call_agent() with its own system
prompt and a small JSON payload, and gets back a parsed dict -- agents
never touch the LLM client directly.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_llm = None


def get_llm():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            temperature=0,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0,
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
                os.getenv(
                    "BEDROCK_MODEL",
                    "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
                ),
            ),
            region_name=os.getenv("AWS_REGION", "eu-north-1"),
            temperature=0,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def call_agent(system_prompt: str, payload: dict) -> dict:
    """Send a system prompt + JSON payload to the LLM and parse a strict-JSON
    reply. Raises ValueError with the raw output if parsing fails, so a bad
    agent response fails loudly instead of silently corrupting the pipeline.
    """
    global _llm
    if _llm is None:
        _llm = get_llm()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(payload, indent=2, default=str)),
    ]
    response = _llm.invoke(messages)
    raw = _strip_code_fence(response.content)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Agent did not return valid JSON. Raw output (truncated):\n{raw[:500]}"
        ) from exc
    print("@@FDD_STEP", flush=True)
    return parsed
