"""Section 11 -- Acceptance Criteria. Tier 4, required (not optional)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You convert the process flow into Given/When/Then scenarios.

First check raw_user_story for any acceptance criteria the story author
already wrote. If present, reconcile: paraphrase their criteria as your
first scenario(s) and set reconciled_with_existing_ac to true -- do not
duplicate content they already specified.

Then add one scenario per happy_path outcome and one per exception_paths
entry. Do not add scenarios for behavior not present in happy_path or
exception_paths.

Output strict JSON with keys: scenarios (array of {name, given, when,
then}), reconciled_with_existing_ac (boolean), assumptions_made (array).
No prose outside the JSON."""


def run(state: dict) -> dict:
    section5 = state.get("sections", {}).get("5", {})
    payload = {
        "raw_user_story": state["raw_user_story"],
        "happy_path": section5.get("happy_path"),
        "exception_paths": section5.get("exception_paths"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "11", "agent11_acceptance_criteria", result)
