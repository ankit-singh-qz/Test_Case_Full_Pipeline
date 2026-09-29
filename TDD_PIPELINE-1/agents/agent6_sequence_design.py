"""Section 6 -- Sequence / Interaction Design, optional for small tier. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """Unpack happy_path into a call sequence between the components you were
given -- do not invent a component or a step not grounded in either input.

RULES:
1. Every sequence step must cite an fdd_req_id from happy_path.
2. Every from_component/to_component must be a name from the components
   input. Never invent an intermediate hop (e.g. a cache check) unless a
   component for it already exists in the input.
3. If components has only one entry, output a single self-call sequence
   -- don't manufacture a multi-hop diagram to look more detailed.

Output strict JSON: sequence (array of {step, from_component,
to_component, fdd_req_id}), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    section5 = (state.get("fdd_sections") or {}).get("5") or {}
    tdd_agent2 = (state.get("tdd_sections") or {}).get("2") or {}
    payload = {
        "happy_path": section5.get("happy_path"),
        "components": tdd_agent2.get("components"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "6", "agent6_sequence_design", result)
