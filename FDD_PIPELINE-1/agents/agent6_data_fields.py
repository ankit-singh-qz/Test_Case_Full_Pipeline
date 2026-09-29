"""Section 6 -- Data & Field Specifications. Tier 3 (parallel with Agent 5, 7)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You extract only the data fields that the functional requirements actually
name or unavoidably imply -- never pad this list to look thorough. Do not
add fields with no textual or logical basis in the requirements.

Do not define storage, persistence, or structure for anything listed in
out_of_scope -- even if a requirement references it. If a requirement
mentions something whose definition is out_of_scope (e.g. "revenue
management constraints" when defining those constraints is explicitly
excluded), you may still list it as a field this system CONSUMES, but
set persistence to "external / not defined by this system" rather than
"database" -- do not imply this system owns or stores something its own
scope excludes defining.

validation_rules must contain ONLY data-hygiene constraints (non-empty,
max length, numeric range, format pattern, uniqueness). Never put a
behavioral rule or trigger condition (e.g. "must trigger X if changed")
in validation_rules -- that belongs in Section 4/5, not here.

For each field, infer a reasonable data type and one or two validation
rules from ordinary data hygiene. If a specific constraint isn't
derivable, state "constraint not specified in source" rather than
inventing a number.

Output strict JSON with keys: fields (array of {field_name, data_type,
validation_rules, persistence}), assumptions_made (array). No prose
outside the JSON."""


def run(state: dict) -> dict:
    sections = state.get("sections", {})
    section2 = sections.get("2", {})
    section4 = sections.get("4", {})
    payload = {
        "raw_user_story": state["raw_user_story"],
        "requirements": section4.get("requirements"),
        "out_of_scope": section2.get("out_of_scope"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "6", "agent6_data_fields", result)