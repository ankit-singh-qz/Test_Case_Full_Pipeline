"""Section 5 -- API & Integration Contracts. Tier 2 (uses Agent 4's output from this run)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """One contract per system boundary implied by requirements or dependencies.

RULES:
1. request_fields and response fields must use ONLY field names present
   in the columns input -- do not invent a field the data model doesn't
   have. Each column may include a "target_table" key (which table it
   belongs to) -- ignore this key entirely; it is storage detail
   irrelevant to the API contract. Use the column's "name" regardless of
   which table it lives in.
2. error_responses: each error code must map to a specific scenario in
   error_matrix (cite it in maps_to_fdd_scenario). If error_matrix is
   empty/absent, only include a generic validation-failure response, and
   log in decisions_made that specific error codes need error_matrix
   input to be defined precisely.
3. Do not invent an endpoint for a capability not present in requirements.

Output strict JSON: endpoints (array of {route, request_fields,
success_response, error_responses}), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section4 = fdd.get("4") or {}
    section7 = fdd.get("7") or {}
    section9 = fdd.get("9")
    tdd_agent4 = (state.get("tdd_sections") or {}).get("4") or {}
    payload = {
        "requirements": section4.get("requirements"),
        "internal_dependencies": section7.get("internal_dependencies"),
        "external_dependencies": section7.get("external_dependencies"),
        "columns": tdd_agent4.get("columns"),
        "error_matrix": (section9 or {}).get("error_matrix"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "5", "agent5_api_contracts", result)