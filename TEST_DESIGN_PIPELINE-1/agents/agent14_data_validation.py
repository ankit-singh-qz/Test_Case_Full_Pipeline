"""Section 14 -- Data Validation (DV) scenarios. Tier 3 (uses Agent 4, 5,
and 7's own-run output -- consumes Agent 7's already-derived field
partitions instead of re-reading raw FDD-6 itself)."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Data Validation (DV) scenarios: correctness, format, and
constraint checks for individual fields. You do not test boundary EDGE
values (Boundary Testing's job -- exactly-at-the-limit values) or invalid
ACTIONS/flows (Negative Testing's job) -- your scope is type, format,
enum, required-ness, and referential/uniqueness constraints for each
field, using representative (not edge) invalid values.

RULES:
1. One scenario per field in field_partitions covering its valid
   representative case (accepted). Then, for that SAME field, write ONE
   additional scenario that covers ALL of its non-boundary invalid
   categories together (wrong type, wrong format, missing/null when
   required, wrong enum value, duplicate where uniqueness is required)
   -- list each invalid value tested and its own expected outcome inside
   that single scenario's preconditions/expected_result (e.g. as a
   "case: input -> expected" list), rather than opening a separate
   scenario per category. Only split a field's invalid cases into more
   than one scenario if two categories genuinely need different
   preconditions or exercise different code paths (e.g. one is a
   request-body format check, another is a DB-level uniqueness check
   that requires a pre-existing row) -- do not split just because the
   categories have different names. Skip anything that is "exactly at /
   one past" a stated min/max/length -- that belongs to BT.
2. Use tdd_column_constraints to add DB-level checks not visible from
   field_partitions alone (CHECK constraints, NOT NULL, enum lists,
   uniqueness) -- one scenario per constraint not already covered.
3. expected_result must state the concrete outcome: the validation
   error code/message if known from field_partitions/
   tdd_column_constraints, or "rejected with a validation error" if the
   exact code is not available. A missing error code is a missing fact,
   not a blocker: note it in assumptions_made and leave
   blocked_by_issue null.
4. design_technique is "Equivalence Partitioning" for type/format/enum
   scenarios; use "Boundary Value Analysis" only if a length/count
   constraint genuinely has no dedicated BT boundary scenario (rare --
   prefer EP by default).
5. priority: P1 for any field marked api_exposed with a DB-level CHECK
   constraint (a bad value could reach persistent storage); P2
   otherwise.
6. level: "API" if the field is api_exposed, otherwise "Integration"
   (DB-level constraint checks).
7. scenario_id format: DV-01, DV-02, ...
8. Never write out a string longer than 16 characters. If a value in
   field_partitions is already a "<string of N chars>" descriptor, copy
   that descriptor. Do not count characters by typing them, and never
   use a code-like expression such as "A".repeat(N).

SELF-CHECK: for each field, did you open more than one invalid-case
scenario without a genuine preconditions/code-path difference between
them? If so, merge them into a single scenario. Separately: does any
scenario here duplicate an exact boundary value (exactly-at-limit or
one-past-limit)? If so, remove it -- that is Boundary Testing's
scenario, not yours. If any string value is longer than 16 characters,
replace it with the "<string of N chars>" descriptor.

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    test_sections = state.get("test_sections") or {}
    test4 = test_sections.get("4") or {}
    test5 = test_sections.get("5") or {}
    test7 = test_sections.get("7") or {}
    tdd4 = (state.get("tdd_sections") or {}).get("4") or {}
    payload = {
        "field_partitions": test7.get("fields"),
        "tdd_column_constraints": [
            {"name": c.get("name"), "constraints": c.get("constraints")}
            for c in (tdd4.get("columns") or [])
            if isinstance(c, dict)
        ],
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "14", "agent14_data_validation", result)
