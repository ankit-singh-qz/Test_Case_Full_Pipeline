"""Section 10 -- Localization & Compliance. Tier 4, optional."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You only produce content if persona_definition or fields clearly imply one
of: multiple regions/languages, payment/card data (PCI-DSS), health data
(HIPAA), EU/personal data (GDPR), or an accessibility requirement.

First decide "triggered": true only if such a signal genuinely exists in
the input -- not by default. If triggered is false, return empty arrays
for the three note fields and do not pad them with generic compliance
boilerplate.

Output strict JSON with keys: triggered (boolean), localization_notes
(array), compliance_notes (array), accessibility_notes (array),
assumptions_made (array). No prose outside the JSON."""


def run(state: dict) -> dict:
    sections = state.get("sections", {})
    section2 = sections.get("2", {})
    section6 = sections.get("6", {})
    payload = {
        "persona_definition": section2.get("persona_definition"),
        "fields": section6.get("fields"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "10", "agent10_localization_compliance", result)
