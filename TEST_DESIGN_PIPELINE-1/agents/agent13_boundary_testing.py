"""Section 13 -- Boundary Testing (BT) scenarios. Tier 3 (uses Agent 4, 5,
and 7's own-run output -- consumes Agent 7's already-derived field
partitions instead of re-reading raw FDD-6/TDD-4 itself)."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Boundary Testing (BT) scenarios: minimum, maximum, and
edge-limit conditions. You do not test general invalid formats (Data
Validation's job) or invalid actions (Negative Testing's job) -- only the
values sitting exactly at, just below, or just above a stated numeric or
length boundary, and any timing boundary from retry/timeout/backoff
schedules.

RULES:
1. Do NOT invent a boundary value. Every value you cite must come from
   field_partitions (a field's stated min/max/length, read from its
   rule/valid_examples/invalid_examples) or resilience_numerics (a
   stated timeout/retry-count/backoff cap). If a field has only one
   side of a boundary stated (e.g. only a minimum), only test that
   side, and note in assumptions_made that the other side is undefined
   rather than making one up.
2. For a field with a numeric boundary (min or max = X), write up to
   four scenarios: exactly X, and the value one unit past X in whichever
   direction is invalid, PLUS if BOTH min and max exist, the same for
   the other side -- one scenario per boundary edge, not one scenario
   covering multiple edges.
3. For a length boundary, write: exactly the max length (valid) and
   max length + 1 (invalid). Same one-scenario-per-edge rule. Never
   write out a string longer than 16 characters. Copy the
   "<string of N chars>" descriptor already in field_partitions. Do
   not count characters by typing them, and never use a code-like
   expression such as "A".repeat(N).
4. For a resilience numeric (e.g. a stated timeout), write: just under
   the threshold (succeeds) and just over it (fails/triggers the next
   behavior), citing the exact numbers from resilience_numerics.
5. EXACTLY ONE scenario per boundary edge, and only for an edge that is
   a stated min, max, or length. Do not write a second scenario for the
   same edge from a different angle, and do not treat any of these as a
   boundary at all -- they belong to other agents:
   a. Decimal precision. "2 decimal places accepted, 3 rejected" is a
      format rule, so it is Data Validation's, not a boundary.
   b. A type, format, enum, null, or uniqueness check, even when the
      rule that states it also states a length.
   c. A timestamp's format or timezone. Only a stated timing THRESHOLD
      from resilience_numerics is a boundary.
   If a field's rule states no numeric or length limit at all, write no
   scenario for that field.
6. design_technique is always "Boundary Value Analysis".
7. priority: P1 if field_partitions marks the field api_exposed and its
   rule implies money, identity, or a count-based state; P2 otherwise.
8. level: "API" if the field is api_exposed, otherwise "Unit".
9. scenario_id format: BT-01, BT-02, ...

SELF-CHECK: does every boundary value in every scenario literally appear
in field_partitions or resilience_numerics? Delete any scenario where it
does not. Then check for the two failures this section is prone to: two
scenarios covering the same edge of the same field (keep one), and a
scenario testing a format, precision, or enum rather than a limit (delete
it -- Data Validation covers it). If any string value is longer than 16
characters, replace it with the "<string of N chars>" descriptor from
field_partitions.

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    test_sections = state.get("test_sections") or {}
    test4 = test_sections.get("4") or {}
    test5 = test_sections.get("5") or {}
    test7 = test_sections.get("7") or {}
    tdd11 = (state.get("tdd_sections") or {}).get("11") or {}
    payload = {
        "field_partitions": test7.get("fields"),
        "resilience_numerics": tdd11.get("mechanisms"),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "13", "agent13_boundary_testing", result)
