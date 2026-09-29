"""Section 11 -- Positive Testing (PT) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Positive Testing (PT) scenarios: valid inputs and expected
outcomes that must succeed. This is one of ten testing-technique agents;
your scope is ONLY the happy path -- never write a negative, boundary, or
error scenario here (those belong to other agents).

RULES:
1. One scenario per functional requirement (fdd_requirements) covering
   its stated happy-path behavior, plus one per given/when/then in
   fdd_acceptance_scenarios that is not already a paraphrase of a
   requirement you already covered (do not duplicate the same behavior
   twice).
2. If a tdd_success_response entry defines the response fields for the
   endpoint that realizes a requirement, reference those fields in
   expected_result concretely (e.g. "response includes the updated
   value and its update timestamp") rather than a vague "succeeds".
3. If tdd_sequence gives a multi-step flow, write one end-to-end
   scenario following that sequence from first to last step.
4. design_technique is "Equivalence Partitioning" for every scenario
   here -- valid-class inputs are what PT tests.
5. priority: P1 if the requirement is the core capability the feature
   exists for (judge from feature naming/shall_statement centrality);
   P2 for supporting/secondary requirements.
6. blocked_by_issue: see the rule at the end of this prompt. For a
   happy-path scenario it is almost always null -- a contradiction about
   what happens when something FAILS does not change what a successful
   request returns.
7. level: "Integration" or "API" or "End-to-end" depending on whether
   the scenario exercises one component or a full chain -- never
   "Unit" here (PT scenarios exercise real behavior, not isolated
   logic).
8. scenario_id format: PT-01, PT-02, ... two digits, sequential.

SELF-CHECK: does any scenario here describe an invalid input, a failure,
or an edge/boundary value? If so, remove it -- it belongs to a different
agent.

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section4 = fdd.get("4") or {}
    section5 = fdd.get("5") or {}
    section11 = fdd.get("11") or {}
    tdd5 = tdd.get("5") or {}
    tdd6 = tdd.get("6") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "fdd_requirements": section4.get("requirements"),
        "fdd_happy_path": section5.get("happy_path"),
        "fdd_acceptance_scenarios": section11.get("scenarios"),
        "tdd_success_responses": [
            {"route": e.get("route"), "success_response": e.get("success_response")}
            for e in (tdd5.get("endpoints") or [])
            if isinstance(e, dict)
        ],
        "tdd_sequence": tdd6.get("sequence"),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "11", "agent11_positive_testing", result)
