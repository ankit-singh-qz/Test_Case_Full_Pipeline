"""Section 14 -- Deployment & Rollout Plan, optional unless large tier. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. Pick ONE option from rollout_strategy_options -- the FDD agent
   deliberately left this choice open for you to make. State why you
   picked it over the alternatives.
2. Specific percentages/timings (e.g. "2% for 60 minutes") are your
   decision -- log them in decisions_made as chosen defaults, not as
   FDD-derived facts.
3. Check migration_needed before writing your justification. If it is
   false, this is an ADDITIVE feature rollout, not a schema migration --
   do not use the words "migration," "migrating," or "schema migration"
   anywhere in justification or steps. Describe it instead as rolling
   out new functionality/new fields. If migration_needed is true, it is
   appropriate to describe it as a migration.
4. If migration_needed is true, you may also reference migration_notes
   (if given) to explain what specifically is being migrated.

SELF-CHECK: if migration_needed is false, re-read your own justification
-- does it contain the word "migration" anywhere? If so, rewrite it to
describe an additive rollout instead.

Output strict JSON: chosen_strategy, justification, steps (array),
decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    section13 = (state.get("fdd_sections") or {}).get("13") or {}
    payload = {
        "rollout_strategy_options": section13.get("rollout_strategy_options"),
        "migration_needed": section13.get("migration_needed"),
        "migration_notes": section13.get("migration_notes"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "14", "agent14_deployment", result)