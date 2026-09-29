"""Expands test_design_pipeline's Section 17 -- Security Testing (SEC)
scenarios into step-level test cases. Tier 1 (all ten technique agents
are independent -- none depends on another)."""
from agents.common import (
    BLOCKED_OR_READY,
    IO_SCHEMA,
    expand_test_cases,
    merge_section,
)

SECTION_ID = "17"
AGENT_NAME = "agent17_security_testing"

SYSTEM_PROMPT = """You expand already-decided Security Testing (SEC) scenarios into
execution-ready, step-level test cases. You do not invent new scenarios,
change their scope, or second-guess their priority -- your only job is
turning each scenario's generic expected_result into concrete numbered
steps with real data, using the field examples, environment stubs, and
data sets already provided (e.g. token/scope test data).

RULES:
1. Produce exactly one test_case entry per entry in `scenarios` -- never
   skip one, never merge two into one.
2. test_case_id is "TC-SEC-NN" using the same two-digit number as the
   source scenario_id (SEC-01 -> TC-SEC-01). scenario_id must be copied
   verbatim from the source scenario (back-link).
   title and objective are required on every test case, including
   blocked ones. title is a short test title taken from the scenario
   title (same scope -- do not invent a different test). objective is
   one sentence stating what this test verifies; it is the intent, not
   the step-level expected result and not a copy of
   overall_expected_result.
3. For a scenario whose blocked_by_issue is null: set status "ready".
   - preconditions: rewrite the scenario's own preconditions as
     concrete statements, naming the exact token/scope/credential
     variant from `data_sets` (e.g. "token scoped to pricing:read only")
     that the scenario requires.
   - steps: an ordered array of {step_no, action, test_data,
     expected_result}. test_data cites the literal token/scope/
     credential value from `data_sets` when the step touches
     authentication/authorization. expected_result is the observable
     outcome of THAT step alone (the exact status code cited in the
     scenario, if any), never the whole scenario.
   - overall_expected_result restates the scenario's own expected_result,
     made concrete with the same literal values used in the steps.
   - priority is copied verbatim from the scenario -- never re-derived
     (note: source SEC scenarios are typically all P1; preserve that).
   - automatable is true unless the outcome genuinely cannot be
     asserted by a script with the given data.
4. For a scenario whose blocked_by_issue is NOT null: apply the
   BLOCKED VERSUS READY rule at the end of this prompt. It is the same
   for every technique -- block only when two real answers would make
   this test pass or fail differently, and treat a missing number,
   maximum, error code, or schema as "ready" with a stated assumption.
5. Never cite a token scope, credential variant, or encryption standard
   that is not literally present in `scenarios`, `fields`, or
   `data_sets`.

SELF-CHECK: for every "ready" test case, does the credential/scope in
test_data appear verbatim in `data_sets`? For every "blocked" test case,
is the reason a genuine open behavioral question, not just a
missing-but-inferable detail?

Return one JSON object matching the input and output schema. JSON only."""


def run(state: dict) -> dict:
    test_design = state.get("test_design_sections") or {}
    section = test_design.get(SECTION_ID) or {}
    scenarios = section.get("scenarios") or []

    if not scenarios:
        result = {
            "test_cases": [],
            "assumptions_made": [
                "No Security Testing scenarios were produced by test_design_pipeline "
                "for this feature; nothing to expand."
            ],
        }
        return merge_section(state, SECTION_ID, AGENT_NAME, result)

    issues_section = test_design.get("4") or {}
    env_section = test_design.get("6") or {}
    fields_section = test_design.get("7") or {}
    payload = {
        "scenarios": scenarios,
        "issues": issues_section.get("issues"),
        "fields": fields_section.get("fields"),
        "data_sets": env_section.get("data_sets"),
        "environment_needs": env_section.get("environment_needs"),
    }
    result = expand_test_cases(SYSTEM_PROMPT + IO_SCHEMA + BLOCKED_OR_READY, payload)
    return merge_section(state, SECTION_ID, AGENT_NAME, result)
