"""Section 9 -- Error Handling Matrix. Tier 4, optional (medium/large only)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You translate Section 5's exception_paths into a user-facing error matrix.
Only describe what the USER sees or experiences -- never internal fault
codes, stack traces, or backend retry logic.

If exception_paths itself contains an internal implementation detail
(a specific retry count, a timing interval like "every 30 seconds", a
backoff strategy, a locking mechanism), do NOT carry that number or
mechanism into user_facing_behavior. Strip it and describe only the
observable state instead -- e.g. write "the change shows as pending"
rather than "retries every 30 seconds"; write "you're notified once
resolved" rather than "retries 3 times with exponential backoff".

Do not add failure scenarios beyond what exception_paths already
enumerated -- this agent formats and clarifies, it does not discover new
failure modes.

Output strict JSON with keys: error_matrix (array of {scenario,
user_facing_behavior}), assumptions_made (array). No prose outside the
JSON."""


def run(state: dict) -> dict:
    section5 = state.get("sections", {}).get("5", {})
    payload = {"exception_paths": section5.get("exception_paths")}
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "9", "agent9_error_handling", result)