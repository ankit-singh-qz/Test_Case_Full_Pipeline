"""Section 16 -- Performance Testing (PERF) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Performance Testing (PERF) scenarios: response time,
throughput, load, and soak conditions.

RULES:
1. If fdd_performance_target contains a concrete numeric threshold
   (e.g. a stated time window), write a scenario measuring end-to-end
   completion against that exact threshold, at a load level ONLY if one
   is stated somewhere in the inputs -- otherwise write the scenario
   with expected_result citing the threshold and record the undefined
   load profile in assumptions_made.
2. If fdd_performance_target/fdd_concurrency_note has NO numeric
   threshold at all, still write one scenario naming what SHOULD be
   measured (e.g. the specific latency the feature implies) and set
   expected_result to "no pass/fail threshold defined". Do not invent a
   number to fill the gap. An undefined threshold or load profile is a
   missing fact, so leave blocked_by_issue null -- record it in
   assumptions_made instead.
3. If tdd_metrics lists specific measurable metrics (e.g. p95/p99
   latency, a success-rate metric), write one scenario per metric
   verifying it is emitted and moves correctly under the failure/load
   condition it tracks -- cite the metric name.
4. If tdd_concurrency_applicable is true, add one load scenario
   combining concurrent updates with the performance target (contention
   should not push latency past the stated/undefined threshold).
5. Add one long-duration/soak scenario only if fdd_tier is "large"
   (sustained load over an extended period, checking for degradation);
   otherwise omit it.
6. design_technique is "Fault Injection" only for a recovery-after-
   outage scenario; "Boundary Value Analysis" when testing exactly at a
   stated threshold; "Inspection" for a metric-presence-only check.
7. priority: P1 if tied to a stated SLA/threshold that is a core
   requirement; P2 for load/contention scenarios with no hard SLA; P3
   for soak/observability-only checks.
8. level: "Performance".
9. scenario_id format: PERF-01, PERF-02, ...

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section12 = fdd.get("12") or {}
    tdd3 = tdd.get("3") or {}
    tdd13 = tdd.get("13") or {}
    tdd9 = tdd.get("9") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "fdd_tier": state.get("fdd_tier"),
        "fdd_performance_target": section12.get("performance_target"),
        "fdd_concurrency_note": section12.get("concurrency_note"),
        "tdd_tech_stack_notes": tdd3.get("decisions_made") if tdd3.get("applicable") else None,
        "tdd_metrics": tdd13.get("metrics"),
        "tdd_concurrency_applicable": tdd9.get("applicable"),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "16", "agent16_performance_testing", result)
