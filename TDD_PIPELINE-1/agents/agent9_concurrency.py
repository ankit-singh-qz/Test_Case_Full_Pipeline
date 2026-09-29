"""Section 9 -- Concurrency & Race Condition Handling, optional/required if flagged. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. applicable is true if EITHER:
   (a) exception_paths contains a scenario describing concurrent/
       simultaneous access or update conflicts, OR
   (b) fdd_risks contains a risk mentioning concurrent updates, race
       conditions, or simultaneous access to the same entity -- even if
       exception_paths itself is silent on it. The FDD's own review
       agent may have flagged this concern in risks without it having
       been carried into a formal exception path; don't drop a concern
       just because it only appears in one of the two inputs.
2. If applicable is true because of (b) only -- i.e. exception_paths had
   nothing but fdd_risks did -- say so explicitly in
   reconciliation_notes, e.g. "No concurrency exception path was defined
   in the FDD's process flow, but the FDD's own risk analysis flagged
   [quote the risk] -- addressing it here as a precaution."
3. lock_strategy (optimistic vs pessimistic) is YOUR engineering
   decision -- the FDD deliberately doesn't specify this. Make the
   choice, state it plainly, and log it in decisions_made with your
   reasoning (e.g. "optimistic chosen: FDD implies low write contention
   since only one persona modifies pricing").
4. If applicable is false, leave lock_strategy null. This should now
   only happen if NEITHER exception_paths NOR fdd_risks mentions any
   concurrency concern at all.

Output strict JSON: applicable (boolean), lock_strategy,
reconciliation_notes, decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section5 = fdd.get("5") or {}
    section8 = fdd.get("8") or {}
    payload = {
        "exception_paths": section5.get("exception_paths"),
        "fdd_risks": section8.get("risks"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "9", "agent9_concurrency", result)