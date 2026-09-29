"""Section 7 -- Dependencies. Tier 3 (parallel with Agent 5, 6)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You identify what other internal modules or external services this story
functionally relies on -- WHAT is involved, never HOW it's called. Do not
output API endpoints, payload formats, or protocol names -- that is
technical design, out of scope for an FDD.

Classification rule: if out_of_scope says this system does not define,
calculate, or integrate with something (e.g. demand metrics are "already
provided" or come from a source this story doesn't integrate with), that
thing is an EXTERNAL dependency, not internal -- even if it sounds like
it could be part of the same company's systems. Internal dependencies
are only things this story's own requirements imply the system builds or
directly manages.

Internal dependencies: existing internal systems/modules the requirements
imply interaction with, that this system itself manages or was built for.

External dependencies: third-party or upstream services implied by the
story OR by out_of_scope's exclusions. If the story implies none, return
an empty array -- do not invent a dependency for the sake of filling the
section.

Output strict JSON with keys: internal_dependencies (array),
external_dependencies (array), assumptions_made (array). No prose outside
the JSON."""


def run(state: dict) -> dict:
    sections = state.get("sections", {})
    section2 = sections.get("2", {})
    section4 = sections.get("4", {})
    payload = {
        "in_scope": section2.get("in_scope"),
        "out_of_scope": section2.get("out_of_scope"),
        "requirements": section4.get("requirements"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "7", "agent7_dependencies", result)