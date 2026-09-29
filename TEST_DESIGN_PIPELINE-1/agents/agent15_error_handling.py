"""Section 15 -- Error Handling (EH) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Error Handling (EH) scenarios: how the system behaves
INTERNALLY when a dependency or infrastructure failure occurs -- retries,
circuit breakers, fallback/rollback, and recovery. You do not test what
the caller sees for a single bad request (Negative Testing's job) -- your
scope is the recovery MECHANICS behind a failure, even when they share
the same triggering condition as an NT scenario.

RULES:
1. One scenario per entry in tdd_resilience_mechanisms, testing the
   mechanism's parameters concretely (e.g. "after N consecutive
   failures, the circuit opens; requests fail fast until the timeout
   elapses; then a probe request is allowed through") -- cite the exact
   numbers from that entry's parameters, never invented ones.
2. If tdd_lock_strategy or tdd_concurrency_notes describes a conflict/
   race condition, add one scenario for the conflict-detection and
   retry/rejection behavior it describes.
3. If tdd_kill_switch_fallback is non-null and describes suspending
   writes, add one scenario verifying that behavior specifically (reads
   still work, writes are suspended, exactly as described -- do not
   extend it to claim any pre-existing table/column is affected beyond
   what tdd_kill_switch_fallback states).
4. Cross-reference fdd_exception_paths and fdd_error_matrix only to
   confirm a resilience mechanism traces back to a real failure
   scenario (cite it in src_refs) -- do not invent a new failure
   scenario here that is not in either input.
5. design_technique is "Fault Injection" for retry/circuit-breaker/
   fallback scenarios, "State Transition" for circuit-breaker or
   kill-switch state changes (closed/open/half-open, or on/off), and
   "Concurrency/Race Testing" for the lock-conflict scenario.
6. Any mechanism whose parameters mention rolling back another change
   on failure is always P1 (it protects atomicity/integrity).
   Otherwise: P1 if the mechanism protects data consistency, P2 if it
   is a pure availability/retry concern.
7. level: "Integration" for dependency-failure scenarios, "Unit" for a
   pure backoff/circuit-breaker calculation scenario with no external
   dependency involved.
8. scenario_id format: EH-01, EH-02, ...

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section5 = fdd.get("5") or {}
    section9 = fdd.get("9") or {}
    tdd9 = tdd.get("9") or {}
    tdd11 = tdd.get("11") or {}
    tdd15 = tdd.get("15") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "fdd_exception_paths": section5.get("exception_paths"),
        "fdd_error_matrix": section9.get("error_matrix"),
        "tdd_resilience_mechanisms": tdd11.get("mechanisms"),
        "tdd_lock_strategy": tdd9.get("lock_strategy"),
        "tdd_concurrency_notes": tdd9.get("reconciliation_notes"),
        "tdd_kill_switch_fallback": (
            tdd15.get("fallback_behavior") if tdd15.get("applicable") else None
        ),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "15", "agent15_error_handling", result)
