"""Section 12 -- Security Architecture. Tier 1 (parallel with 1, 2, 4) -- required always."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. token_scopes must reflect the actual persona and access level from
   persona_definition -- not a generic example with a placeholder
   org/user name from a different story.
2. masking_rules: only populate if compliance_notes is present and names
   sensitive data. Otherwise leave empty.
3. transport_encryption and at_rest_encryption baseline choices (TLS,
   encryption at rest) are reasonable defaults -- state them, and log the
   specific standard/algorithm choice in decisions_made since the FDD
   doesn't dictate a specific cipher suite.

Output strict JSON: transport_encryption, at_rest_encryption, authn_authz,
token_scopes (array), masking_rules (array), decisions_made (array).
JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section3 = fdd.get("3") or {}
    section2 = fdd.get("2") or {}
    section10 = fdd.get("10")
    payload = {
        "pre_conditions": section3.get("pre_conditions"),
        "persona_definition": section2.get("persona_definition"),
        "compliance_notes": (section10 or {}).get("compliance_notes"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "12", "agent12_security", result)
