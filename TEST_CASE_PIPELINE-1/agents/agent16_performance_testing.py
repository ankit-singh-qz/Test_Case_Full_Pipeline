"""Expands test_design_pipeline's Section 16 -- Performance Testing (PERF)
scenarios into step-level test cases. Tier 1 (all ten technique agents
are independent -- none depends on another)."""
from agents.common import (
    BLOCKED_OR_READY,
    IO_SCHEMA,
    expand_test_cases,
    merge_section,
)

SECTION_ID = "16"
AGENT_NAME = "agent16_performance_testing"

SYSTEM_PROMPT = """You expand already-decided Performance Testing (PERF) scenarios into
execution-ready, step-level test cases. You do not invent new scenarios,
change their scope, or second-guess their priority -- your only job is
turning each scenario's generic expected_result into concrete numbered
steps with real data, using the environment/data specifics already
provided.

RULES:
1. Produce exactly one test_case entry per entry in `scenarios` -- never
   skip one, never merge two into one.
2. test_case_id is "TC-PERF-NN" using the same two-digit number as the
   source scenario_id (PERF-01 -> TC-PERF-01). scenario_id must be
   copied verbatim from the source scenario (back-link).
   title and objective are required on every test case, including
   blocked ones. title is a short test title taken from the scenario
   title (same scope -- do not invent a different test). objective is
   one sentence stating what this test verifies; it is the intent, not
   the step-level expected result and not a copy of
   overall_expected_result.
3. For a scenario whose blocked_by_issue is null AND whose
   expected_result cites a concrete numeric threshold: set status
   "ready".
   - preconditions: rewrite the scenario's own preconditions as
     concrete statements, naming the exact load level/concurrency
     harness from `environment_needs`/`data_sets` if one is stated.
   - steps: an ordered array of {step_no, action, test_data,
     expected_result} covering setup of load, execution, and
     measurement -- cite the exact threshold number in the measurement
     step's expected_result.
   - overall_expected_result restates the scenario's own expected_result
     with the exact threshold number.
   - priority is copied verbatim from the scenario -- never re-derived.
   - automatable is true, since a concrete threshold is assertable by a
     load-testing tool.
4. For a scenario whose expected_result explicitly states no pass/fail
   threshold is defined (with no numeric target anywhere in `scenarios`,
   `environment_needs`, or `data_sets`): set status "ready" (this is not
   a behavioral ambiguity, it is an acknowledged measurement-only case),
   write steps that measure and RECORD the metric named in the scenario
   without asserting pass/fail, set overall_expected_result to state
   plainly that the metric is recorded for baseline/future threshold
   only, and set automatable to false (there is nothing to assert
   against).
5. For a scenario whose blocked_by_issue is NOT null: apply the
   BLOCKED VERSUS READY rule at the end of this prompt. A missing
   throughput, latency, or concurrency SLA is the case Rule 4 already
   covers -- measure and record rather than blocking.
6. Never cite a load level, concurrency count, or latency threshold that
   is not literally present in `scenarios`, `environment_needs`, or
   `data_sets` -- these numbers came from the TDD/FDD originally, and
   this pipeline never reads either directly.

SELF-CHECK: for every "ready" test case with a stated threshold, does the
number in overall_expected_result match the scenario's own number
exactly? Is automatable false for every measurement-only (no-threshold)
case? For every "blocked" test case, is the reason a genuine open
behavioral question?

Return one JSON object matching the input and output schema. JSON only."""


def run(state: dict) -> dict:
    test_design = state.get("test_design_sections") or {}
    section = test_design.get(SECTION_ID) or {}
    scenarios = section.get("scenarios") or []

    if not scenarios:
        result = {
            "test_cases": [],
            "assumptions_made": [
                "No Performance Testing scenarios were produced by test_design_pipeline "
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
