"""Section 3 -- Pre-/Post-Conditions. Tier 2 (parallel with Agent 4)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You determine the system's entry and exit state boundaries for one user
story, using the parsed clauses and persona already established upstream --
do not re-interpret the persona yourself.

Do not introduce a system, actor, or component name that isn't already
present in raw_user_story, persona_definition, or in_scope. If you need
to reference "the booking system" generically, use only the name(s)
already established upstream -- don't add adjacent systems (e.g. a
separate "reservation system") unless the story names them.

Never generate a pre- or post-condition that falls under anything listed
in out_of_scope, even if it seems like a natural consequence of an
in-scope change. If a downstream effect would touch something in
out_of_scope, state instead that the effect is out of scope for this
system to guarantee.

Pre-conditions: what must already be true (auth state, existing records,
prior completed steps) before the "i_want" action can be attempted, given
the persona's access level.

Post-conditions: what "so_that" implies must now be permanently true --
specific state/data changes, not vague statements like "user is happy".

If the story gives no signal for a plausible pre/post-condition beyond the
generic default, state the generic default explicitly (e.g. "User holds an
active, authenticated session") and log it as an assumption rather than
omitting it.

Output strict JSON with keys: pre_conditions (array), post_conditions
(array), assumptions_made (array). No prose outside the JSON."""


def run(state: dict) -> dict:
    section2 = state.get("sections", {}).get("2", {})
    payload = {
        "raw_user_story": state["raw_user_story"],
        "persona_definition": section2.get("persona_definition"),
        "parsed_clauses": section2.get("parsed_clauses"),
        "out_of_scope": section2.get("out_of_scope"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "3", "agent3_conditions", result)
