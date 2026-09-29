"""Section 7 -- Background Jobs & Schedulers, optional. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. Set applicable to true ONLY if happy_path or performance_target
   explicitly describes a recurring/scheduled process (a stated polling
   interval, or wording that implies continuous background monitoring
   rather than a one-time event-triggered action).
2. An SLA like "must react within 5 minutes of an event" is an
   event-driven trigger, NOT evidence of a cron job -- do not treat SLA
   wording as cadence evidence.
3. If applicable is false, leave cadence/duplicate_prevention/
   retry_threshold null and state why in decisions_made.
4. If applicable is true, the cadence value must come from the FDD text
   itself, not a round-number default -- if no exact interval is stated,
   log your chosen interval as a decision, don't present it as derived.

Output strict JSON: applicable (boolean), cadence, duplicate_prevention,
retry_threshold (all string or null), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section5 = fdd.get("5") or {}
    section12 = fdd.get("12") or {}
    payload = {
        "happy_path": section5.get("happy_path"),
        "performance_target": section12.get("performance_target"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "7", "agent7_background_jobs", result)
