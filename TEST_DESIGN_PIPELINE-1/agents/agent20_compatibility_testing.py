"""Section 20 -- Compatibility Testing (COMP) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Compatibility Testing (COMP) scenarios: behavior across
browsers, devices, OS/platforms, and environments. For a backend/API
feature with no browser/device surface, scope this to API-client and
protocol compatibility: transport protocol versions, data format/locale
handling, and behavior across a phased rollout.

RULES:
1. If tdd_transport_encryption states a minimum protocol version (e.g.
   a minimum TLS version), write one scenario confirming that version
   and newer are accepted and older versions are refused -- cite the
   exact version stated, never an invented one.
2. If tdd_timestamp_columns is non-empty, write one scenario confirming
   timestamp format/timezone handling is consistent regardless of
   client locale (only if the input gives a concrete format to check,
   e.g. ISO 8601 -- otherwise note the gap in assumptions_made instead
   of inventing a format).
3. If tdd_rollout_steps describes cohort-based rollout (e.g. percentage
   phases), write one scenario per phase boundary confirming: entities
   inside the cohort get the new behavior, entities outside do not, and
   one scenario confirming behavior is unchanged across a transition
   (e.g. toggling back).
4. If fdd_localization_notes is non-empty, write one scenario per
   distinct region/currency/locale item it names.
5. If none of the above have any basis in the input, output an empty
   scenarios array and state in decisions_made that no
   compatibility-relevant surface (protocol version, locale handling,
   or phased rollout) was found in the input.
6. design_technique is "Equivalence Partitioning" for protocol/locale
   scenarios, "State Transition" for rollout-phase scenarios.
7. priority: P2 by default; P1 only for a protocol-security scenario
   (e.g. rejecting a deprecated TLS version).
8. level: "Deployment" for rollout-phase scenarios, "Integration"
   otherwise.
9. scenario_id format: COMP-01, COMP-02, ...

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), decisions_made (array), assumptions_made (array).
JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section10 = fdd.get("10") or {}
    tdd12 = tdd.get("12") or {}
    tdd14 = tdd.get("14") or {}
    tdd4 = tdd.get("4") or {}
    timestamp_columns = [
        c.get("name")
        for c in (tdd4.get("columns") or [])
        if isinstance(c, dict) and "TIMESTAMP" in (c.get("sql_type") or "").upper()
    ]
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "fdd_localization_notes": section10.get("localization_notes"),
        "tdd_transport_encryption": tdd12.get("transport_encryption"),
        "tdd_timestamp_columns": timestamp_columns,
        "tdd_rollout_steps": tdd14.get("steps") if tdd14.get("chosen_strategy") else None,
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "20", "agent20_compatibility_testing", result)
