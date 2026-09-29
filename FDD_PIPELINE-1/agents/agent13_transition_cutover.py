"""Section 13 -- Transition & Cutover. Tier 4, optional (large tier only)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """This section only runs for large-tier stories.

migration_needed: set true ONLY if a field implies altering or extending
an EXISTING stored data shape (adding a column to an existing table,
changing an existing column's type or constraint). If all new fields
belong to entirely NEW tables/entities (e.g. a brand-new audit log table
that didn't exist before), set migration_needed to FALSE and note in
migration_notes that this is purely additive, not a migration of
existing data.

rollout_strategy_options: name feature-flag, canary, or cold-cutover as
options with one line each on tradeoffs -- do not pick one for the team.

kill_switch_note: state only that a kill-switch is recommended given the
tier, and why (in one sentence). Do NOT describe how it would be
implemented -- no flag names, no granularity (e.g. "independently
disable X and Y"), no specific architecture. That level of detail is
technical design, not functional design.

Output strict JSON with keys: migration_needed (boolean), migration_notes
(string or null), rollout_strategy_options (array), kill_switch_note
(string or null), assumptions_made (array). No prose outside the JSON."""


def run(state: dict) -> dict:
    section6 = state.get("sections", {}).get("6", {})
    payload = {"fields": section6.get("fields"), "tier": state.get("tier")}
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "13", "agent13_transition_cutover", result)