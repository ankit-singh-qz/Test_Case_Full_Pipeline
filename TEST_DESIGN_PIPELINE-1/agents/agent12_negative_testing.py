"""Section 12 -- Negative Testing (NT) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Negative Testing (NT) scenarios: invalid actions or invalid-flow
attempts and how the system must reject or handle them at the request/
action level. You do NOT own field-format validation (that is Data
Validation's job) or internal fault-recovery mechanics (that is Error
Handling's job) -- your scope is: what does the caller see when they
attempt an invalid ACTION or trigger a business-rule rejection.

RULES:
1. One scenario per fdd_exception_paths entry and one per
   fdd_error_matrix entry, merging the two if they clearly describe the
   same failure (same trigger phrase) rather than duplicating.
2. If a tdd_error_response's maps_to_fdd_scenario matches the same
   fdd scenario, cite its HTTP code and message verbatim in
   expected_result. If no tdd_error_response exists for an
   fdd_error_matrix entry, still write the scenario and set
   expected_result to what the FDD alone specifies -- a missing HTTP
   code does not block the scenario, so note it in assumptions_made and
   leave blocked_by_issue null unless the rule at the end of this
   prompt is met.
3. design_technique is "Error Guessing" unless the scenario is better
   modeled as a "Decision Table" (multiple independent conditions
   combining, e.g. constraint pass/fail x audit ok/fail) -- pick
   whichever fits that specific scenario, not a blanket choice for the
   whole section.
4. Do not write a scenario for a single invalid field VALUE (e.g. "a
   negative price") -- that belongs to Data Validation. Do write a
   scenario for an invalid ACTION (e.g. attempting to bypass a
   constraint, calling an endpoint without permission, submitting a
   request for a nonexistent entity, retrying after exhaustion).
5. priority: P1 if the rejection protects data integrity, money, or
   security; P2 otherwise.
6. level: "API" for single-endpoint error-response scenarios,
   "Integration" for scenarios involving a dependency's failure.
7. scenario_id format: NT-01, NT-02, ...

SELF-CHECK: is any scenario here actually testing one field's format or
boundary rather than an invalid action/flow? If so, remove it.

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section5 = fdd.get("5") or {}
    section9 = fdd.get("9") or {}
    tdd5 = tdd.get("5") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    error_responses = []
    for e in (tdd5.get("endpoints") or []):
        if not isinstance(e, dict):
            continue
        for err in e.get("error_responses") or []:
            if isinstance(err, dict):
                error_responses.append({"route": e.get("route"), **err})
    payload = {
        "fdd_exception_paths": section5.get("exception_paths"),
        "fdd_error_matrix": section9.get("error_matrix"),
        "tdd_error_responses": error_responses,
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "12", "agent12_negative_testing", result)
