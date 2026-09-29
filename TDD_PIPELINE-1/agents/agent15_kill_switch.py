"""Section 15 -- Kill-Switch Implementation, optional. Tier 3 (uses Agent 4's schema)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. applicable is true only if kill_switch_note is present and non-null.
2. table_name is the NEW table this feature introduced. existing_table_name
   (if not null) is a PRE-EXISTING table that some columns extend -- it
   already held production data before this feature existed.
3. fallback_behavior must ONLY describe suspending writes to table_name
   (the new table) and to whichever NEW columns were added to
   existing_table_name, if any. NEVER describe disabling, reverting, or
   suspending existing_table_name's pre-existing columns or its prior
   functionality -- that table's original behavior predates this feature
   and a kill-switch for this feature has no business touching it.
4. If existing_table_name is present, name it explicitly in
   fallback_behavior as "extended, not owned" by this feature, and state
   that reverting means the new columns on it stop being written to,
   while the table's pre-existing use is unaffected.
5. config_key naming convention is your decision -- state it plainly.

SELF-CHECK: does fallback_behavior anywhere imply disabling or reverting
existing_table_name's ORIGINAL columns/behavior (the ones not listed as
this feature's new columns)? If so, rewrite -- you only control what this
feature added, not what already existed.

Output strict JSON: applicable (boolean), config_key, fallback_behavior,
decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    section13 = (state.get("fdd_sections") or {}).get("13") or {}
    tdd_agent4 = (state.get("tdd_sections") or {}).get("4") or {}
    payload = {
        "kill_switch_note": section13.get("kill_switch_note"),
        "table_name": tdd_agent4.get("table_name"),
        "existing_table_name": tdd_agent4.get("existing_table_name"),
        "columns": tdd_agent4.get("columns"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "15", "agent15_kill_switch", result)