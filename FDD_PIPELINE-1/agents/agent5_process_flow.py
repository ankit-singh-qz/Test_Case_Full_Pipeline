"""Section 5 -- Process Flow & Logic States. Tier 3 (parallel with Agent 6, 7)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You sequence the functional requirements into a chronological flow.

happy_path: order the requirements (by req_id) into the successful
end-to-end sequence from pre_conditions to post_conditions. Always
required.

alternative_paths: only include a path if it is directly grounded in one
of the requirements provided -- never invent a capability (override,
manual trigger, batch fallback, approval workflow) that isn't described
by any requirement. If a capability is listed in out_of_scope, it cannot
appear here even if it would be a "natural" alternative. If you cannot
point to a specific req_id that implies the alternative route, the
correct answer is an empty array -- do not invent one to fill the field.

exception_paths: for each requirement, name what happens if it fails,
receives invalid input, times out, or hits a permission failure --
described at the FUNCTIONAL level only (what the user or downstream
system experiences), never at the technical/implementation level. Do
NOT invent retry counts, backoff timing, buffering mechanisms, or
locking strategies (e.g. "retries 3 times", "every 30 seconds",
"optimistic locking") -- none of that is functional behavior, and none
of it should be guessed. Instead say what observably happens: e.g.
"pricing remains at its previous value and the failure is logged" is
correct; "retries fetch 3 times with exponential backoff" is not.

state_transitions: only include if pre_conditions or post_conditions
literally mention a status, state, or lifecycle field for an entity. Do
a explicit check before writing anything here: can you quote the exact
phrase in pre_conditions/post_conditions that names a status field? If
no, output an empty array. Do not build a state machine to explain how
you imagine the system works internally -- that is architecture, not a
transcription of what the story/pre/post-conditions actually state.

Output strict JSON with keys: happy_path (array of strings),
alternative_paths (array of {name, description}), exception_paths (array
of {failure_scenario, system_behavior}), state_transitions (array of
{from_state, trigger, to_state}), assumptions_made (array). No prose
outside the JSON."""


def run(state: dict) -> dict:
    sections = state.get("sections", {})
    section2 = sections.get("2", {})
    section3 = sections.get("3", {})
    section4 = sections.get("4", {})
    payload = {
        "pre_conditions": section3.get("pre_conditions"),
        "post_conditions": section3.get("post_conditions"),
        "requirements": section4.get("requirements"),
        "out_of_scope": section2.get("out_of_scope"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "5", "agent5_process_flow", result)