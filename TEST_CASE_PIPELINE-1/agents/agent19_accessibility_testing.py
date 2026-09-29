"""Expands test_design_pipeline's Section 19 -- Accessibility Testing
(ACC) scenarios into step-level test cases. Tier 1 (all ten technique
agents are independent -- none depends on another). Section 19 may
legitimately be empty (applicable: false, no UI surface) -- see the
short-circuit in run() below."""
from agents.common import (
    BLOCKED_OR_READY,
    IO_SCHEMA,
    expand_test_cases,
    merge_section,
)

SECTION_ID = "19"
AGENT_NAME = "agent19_accessibility_testing"

SYSTEM_PROMPT = """You expand already-decided Accessibility Testing (ACC) scenarios into
execution-ready, step-level test cases. You do not invent new scenarios,
change their scope, or second-guess their priority -- your only job is
turning each scenario's generic expected_result into concrete numbered
steps with real data.

RULES:
1. Produce exactly one test_case entry per entry in `scenarios` -- never
   skip one, never merge two into one.
2. test_case_id is "TC-ACC-NN" using the same two-digit number as the
   source scenario_id (ACC-01 -> TC-ACC-01). scenario_id must be copied
   verbatim from the source scenario (back-link).
   title and objective are required on every test case, including
   blocked ones. title is a short test title taken from the scenario
   title (same scope -- do not invent a different test). objective is
   one sentence stating what this test verifies; it is the intent, not
   the step-level expected result and not a copy of
   overall_expected_result.
3. For a scenario whose blocked_by_issue is null: set status "ready".
   - preconditions: rewrite the scenario's own preconditions as
     concrete statements.
   - steps: an ordered array of {step_no, action, test_data,
     expected_result}. expected_result is the observable outcome of
     THAT step alone, never the whole scenario.
   - overall_expected_result restates the scenario's own expected_result
     made concrete.
   - priority is copied verbatim from the scenario -- never re-derived.
   - automatable is true ONLY if the check is one an automated
     accessibility scanner can assert (e.g. contrast ratio, presence of
     an aria-label/alt-text attribute, tab order via DOM inspection).
     Set automatable to false if it requires a human using assistive
     technology to judge (e.g. "a screen reader announces this
     sensibly") -- these need a human reviewer, not a script, even
     though the test case itself is still fully specified and
     executable by a person.
4. For a scenario whose blocked_by_issue is NOT null: apply the
   BLOCKED VERSUS READY rule at the end of this prompt. It is the same
   for every technique -- block only when two real answers would make
   this test pass or fail differently, and treat a missing number,
   maximum, error code, or schema as "ready" with a stated assumption.
5. Never cite a rule or standard that is not literally present in
   `scenarios`.

SELF-CHECK: is automatable false for every case that needs a human with
assistive technology rather than a tool-checkable rule? For every
"blocked" test case, is the reason a genuine open behavioral question?

Return one JSON object matching the input and output schema. JSON only."""


def run(state: dict) -> dict:
    test_design = state.get("test_design_sections") or {}
    section = test_design.get(SECTION_ID) or {}
    scenarios = section.get("scenarios") or []

    if not scenarios:
        result = {
            "test_cases": [],
            "assumptions_made": [
                "No Accessibility Testing scenarios were produced by test_design_pipeline "
                "for this feature (no UI surface evidenced); nothing to expand."
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
