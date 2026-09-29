"""Section 13 -- Observability & Telemetry, optional for small tier. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. Every metric must cite what it tracks -- a specific error_matrix
   scenario or a specific performance_target. No generic "kitchen sink"
   metrics unrelated to what this FDD actually needs monitored.
2. log_fields: standard fields (correlation ID, timestamp, severity) are
   fine as baseline defaults -- state them plainly as a default choice in
   decisions_made rather than presenting them as FDD-derived.

Output strict JSON: log_fields (array), metrics (array of {name,
tracks}), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section9 = fdd.get("9")
    section12 = fdd.get("12") or {}
    payload = {
        "error_matrix": (section9 or {}).get("error_matrix"),
        "performance_target": section12.get("performance_target"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "13", "agent13_observability", result)
