"""Section 7 -- Field-Level Test Design (boundary values and partitions).
Tier 1, always runs. Feeds Agent 6, Agent 13 (BT), and Agent 14 (DV) in
later tiers, so this agent's job is to derive the partitions ONCE rather
than have three later agents each re-derive them from raw FDD/TDD data.

Revision notes (from auditing a real run against its source FDD): rule 1
already told the model to cover every field, but the output still dropped
3 of 15 FDD fields (pricing_validation_result,
pricing_validation_failure_reason, previous_available_seats) with no
assumptions_made entry explaining why. Losing a field here means Agent 13
(boundary) and Agent 14 (data validation) can never test it -- silently.
A prompt instruction alone did not hold across a real run, so this now
also has a deterministic completeness check (_missing_field_names) that
retries once, listing exactly the missing names, the same pattern
test_case_pipeline's expand_test_cases uses for blocked-for-a-missing-fact
cases: one correction pass, not an open-ended loop.

Also: the previous_price row in a real run stated its constraint
("CHECK (previous_price >= 0)") without ever saying whether the field is
nullable, even though the TDD column had no NOT NULL constraint (i.e. it
IS nullable) and this exact fact is what Agent 4 separately flags as an
FDD/TDD disagreement (I-08). Section 7 doesn't resolve that disagreement
-- it isn't Agent 4's job here -- but it should still state the fact
plainly, either side, so a downstream reader isn't missing the one detail
that Agent 4's issue is actually about.
"""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, compact_long_literals, merge_section

# Real output for ~13 fields is ~2K tokens. 8K leaves 4x headroom for a much
# larger schema while still killing a runaway generation early.
MAX_OUTPUT_TOKENS = 8000

SYSTEM_PROMPT = """You build a field-by-field valid/invalid partition table used to derive
boundary and data-validation test cases. You do not write test cases here
-- only the partitions those agents will consume.

RULES:
1. One row per distinct field found in fdd_fields, enriched with the
   matching tdd_column (same name, case-insensitive) if one exists. If a
   field appears in tdd_columns but not fdd_fields (or vice versa),
   include it anyway and note the mismatch in assumptions_made rather
   than silently merging or dropping it. Every field name that appears in
   EITHER fdd_fields or tdd_columns must produce exactly one row. Before
   you finish, count the distinct field names across both inputs and
   confirm your fields array has that many rows -- if it does not, you
   have dropped one; go back and add it rather than explaining the
   omission in assumptions_made.
2. rule: a one-line plain-English statement of the constraint, combining
   the FDD's validation_rules and the matching TDD column's sql_type/
   constraints (e.g. "Non-negative decimal, 2 decimal places,
   DECIMAL(10,2) column, NOT NULL"). State nullability explicitly and
   plainly whenever either side speaks to it: say "NOT NULL" when the
   tdd_column's constraints include it, or "nullable" when the column has
   no NOT NULL constraint, or "nullable (TDD); FDD does not state whether
   null is allowed" when only one side addresses it. Report the fact as
   each source states it -- do not resolve a disagreement between them
   here; that is a separate agent's job, and it can only do that job if
   this row states the fact plainly.
3. valid_examples: 2-4 concrete values that satisfy the rule, including
   any boundary the rule implies (e.g. exactly 0 for a non-negative
   field, exactly the max length for a string).
4. invalid_examples: 2-4 concrete values that violate the rule one
   constraint at a time (wrong type, negative, over length, wrong
   format, one past a stated boundary). Never invent a numeric boundary
   (min/max) that is not stated anywhere in the input -- if only a lower
   bound exists, only give invalid examples for that bound, and note in
   assumptions_made that the upper bound is undefined.
5. api_exposed: true if the field name (case-insensitive) appears in
   api_exposed_field_names, false otherwise.

SELF-CHECK:
1. Does every invalid_example correspond to a constraint that is actually
   stated in the input for that field? Delete any that assume an unstated
   boundary.
2. Count the distinct field names in fdd_fields and tdd_columns combined.
   Count the rows in your fields array. They must match. If yours is
   lower, you dropped a field -- find it and add its row before replying.

Output strict JSON: fields (array of {field_name, rule, valid_examples,
invalid_examples, api_exposed}), assumptions_made (array). JSON only."""

_MISSING_FIELDS_INSTRUCTION = """

CORRECTION (this request follows your previous reply): previous_fields is
the fields array you returned. missing_field_names lists names present in
fdd_fields or tdd_columns that have no row in previous_fields -- you
dropped them.

Return the FULL fields array, every row from previous_fields unchanged,
PLUS one new row for each name in missing_field_names, built the same way
rules 1-5 describe. Do not drop or rewrite any row that was already
present. JSON only, same schema as before."""


def _field_names(fdd_fields, tdd_columns) -> set:
    names = set()
    for item in fdd_fields or []:
        if isinstance(item, dict):
            name = item.get("field_name") or item.get("name")
            if isinstance(name, str):
                names.add(name.lower())
    for item in tdd_columns or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("column_name")
            if isinstance(name, str):
                names.add(name.lower())
    return names


def _missing_field_names(result: dict, all_names: set) -> list:
    present = set()
    for row in (result or {}).get("fields") or []:
        if isinstance(row, dict) and isinstance(row.get("field_name"), str):
            present.add(row["field_name"].lower())
    return sorted(all_names - present)


def _attach_source_refs(result: dict, column_names: set) -> dict:
    """Stamp each row with the sections it was actually read from.

    The prompt used to ask for source_ref, but run() sends no section
    numbers at all, so the model had nothing to answer with and emitted
    the row's position instead -- flight_id got {"fdd": "1", "tdd": "1"},
    current_price {"fdd": "2", "tdd": "2"}, and so on. Agent 13 copied
    those straight into src_refs and Agent 14 rendered them as "FDD-1",
    which left the traceability matrix unable to match any field scenario
    to a requirement. The answer is fixed for this agent: fdd_fields is
    always FDD section 6 and tdd_columns is always TDD section 4, so set
    it here rather than asking."""
    for row in result.get("fields") or []:
        if not isinstance(row, dict):
            continue
        source_ref = {"fdd": "6"}
        if str(row.get("field_name") or "").strip().lower() in column_names:
            source_ref["tdd"] = "4"
        row["source_ref"] = source_ref
    return result


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section6 = fdd.get("6") or {}
    tdd4 = tdd.get("4") or {}
    tdd5 = tdd.get("5") or {}
    endpoints = tdd5.get("endpoints") or []
    exposed_fields = []
    for e in endpoints:
        if not isinstance(e, dict):
            continue
        exposed_fields.extend(e.get("request_fields") or [])
        success = e.get("success_response") or {}
        exposed_fields.extend(success.get("fields") or [])
    fdd_fields = section6.get("fields")
    columns = tdd4.get("columns") or []
    column_names = {
        str(c.get("name")).strip().lower()
        for c in columns
        if isinstance(c, dict) and c.get("name")
    }
    payload = {
        "fdd_fields": fdd_fields,
        "tdd_columns": columns,
        "api_exposed_field_names": sorted({f for f in exposed_fields if f}),
    }
    result = call_agent(
        SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload, max_tokens=MAX_OUTPUT_TOKENS
    )

    all_names = _field_names(fdd_fields, columns)
    missing = _missing_field_names(result, all_names)
    if missing:
        print(
            f"agent7_field_level_design: model dropped {len(missing)} field(s), "
            f"retrying once: {', '.join(missing)}",
            flush=True,
        )
        retry_payload = dict(payload)
        retry_payload["previous_fields"] = result.get("fields")
        retry_payload["missing_field_names"] = missing
        revised = call_agent(
            SYSTEM_PROMPT + CHAR_LIMIT_RULE + _MISSING_FIELDS_INSTRUCTION,
            retry_payload,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        still_missing = _missing_field_names(revised, all_names)
        if still_missing:
            print(
                "agent7_field_level_design: still missing after retry (left out): "
                + ", ".join(still_missing),
                flush=True,
            )
        result = revised

    result = compact_long_literals(result)
    result = _attach_source_refs(result, column_names)
    return merge_section(state, "7", "agent7_field_level_design", result)
