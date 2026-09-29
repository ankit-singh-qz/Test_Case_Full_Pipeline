"""Section 10 -- Async / Event Contracts, optional. Tier 2 (uses Agent 4's output from this run)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. applicable is true ONLY if external_dependencies lists a
   messaging/event-based integration.
2. event_schema fields must come from columns -- do not invent a field
   name not in the data model. Each column may include a "target_table"
   key -- ignore this key entirely; it is storage detail irrelevant to
   the event payload shape. Use the column's "name" and "sql_type"
   regardless of which table it lives in.
3. topic_name should reflect this story's actual entity, not a generic
   placeholder from an unrelated domain.

Output strict JSON: applicable (boolean), topic_name, event_schema
(object), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    section7 = (state.get("fdd_sections") or {}).get("7") or {}
    tdd_agent4 = (state.get("tdd_sections") or {}).get("4") or {}
    payload = {
        "external_dependencies": section7.get("external_dependencies"),
        "columns": tdd_agent4.get("columns"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "10", "agent10_async_events", result)