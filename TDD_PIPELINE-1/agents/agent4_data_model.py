"""Section 4 -- Data Model & Schema. Tier 1 (parallel with 1, 2, 12) -- required always."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """Strict one-to-one mapping from FDD fields -- no invention.

RULES:
1. Every column must map to exactly one field_name from the input
   fields array. Do not add a column the FDD field list doesn't include
   (no created_at/updated_at/id columns unless the FDD listed them).
2. Where a field's validation_rules said "constraint not specified in
   source," you must now make an explicit choice (e.g. a VARCHAR length)
   and log it in decisions_made -- never silently pick a number.
3. indices: only add an index if a field's validation_rules imply
   uniqueness or lookup-by-this-field. Do not add indices speculatively.
4. sql_type should be the closest real SQL type to the FDD's data_type,
   but log any precision/length choice in decisions_made since the FDD
   didn't specify it.
5. Check migration_notes before deciding on table structure. If it says
   some fields extend an EXISTING table while others belong to a new
   entity (e.g. "pricing fields extend the flights table, audit fields
   belong to a new audit_log table"), you MUST reflect that split -- do
   not merge everything into one new table just because it's simpler.
   For each column, set target_table to either "existing" or "new" based
   on which table migration_notes assigns it to. If migration_notes gives
   no such signal, or explicitly says everything is one new entity, one
   table is correct -- set target_table to "new" for every column.
6. If columns split across two tables, output BOTH table_name (for the
   new table) and existing_table_name (the table being extended, taken
   from migration_notes' own wording -- do not guess a name it doesn't
   state). If there's no existing-table split, leave existing_table_name
   null.

SELF-CHECK: does every column trace back to source_fdd_field? Does every
index have a justification you can point to in the input? If
migration_notes mentions an existing table by name, does at least one
column have target_table "existing" -- or did you merge everything into
one table despite the FDD saying otherwise?

Output strict JSON: table_name, existing_table_name (string or null),
columns (array of {name, sql_type, constraints, source_fdd_field,
target_table}), indices (array of {definition, justification}),
decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section6 = fdd.get("6") or {}
    section13 = fdd.get("13") or {}
    payload = {
        "fields": section6.get("fields"),
        "migration_notes": section13.get("migration_notes"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "4", "agent4_data_model", result)