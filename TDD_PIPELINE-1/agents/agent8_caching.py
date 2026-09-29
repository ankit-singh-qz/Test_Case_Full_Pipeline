"""Section 8 -- Caching Strategy, optional. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. applicable is true ONLY if nfr_triggered is true AND performance_target
   implies a latency/freshness requirement a cache would help meet.
2. ttl_seconds must be derived from the FDD's stated freshness window
   (e.g. "reflect within 5 minutes" implies a TTL ceiling around or under
   300 seconds) -- never an arbitrary round number like 900 unless the
   FDD's own number supports it. Cite the FDD wording your number comes
   from.
3. If applicable is false, leave the rest null and state why.

Output strict JSON: applicable (boolean), strategy, ttl_seconds,
invalidation_rule, decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    section12 = (state.get("fdd_sections") or {}).get("12") or {}
    payload = {
        "nfr_triggered": section12.get("triggered", False),
        "performance_target": section12.get("performance_target"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "8", "agent8_caching", result)
