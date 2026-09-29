"""Section 2 -- Purpose & Scope. Tier 1, always runs."""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You define what this test design covers and what it deliberately excludes,
for a Test Case Design Document. This section is the planning layer only
-- it does not write test cases, only states what will and will not be
tested.

RULES:
1. in_scope must be built from: fdd_in_scope, the feature names in
   fdd_requirements (group by feature, do not list every req_id
   individually), and tdd_endpoints (name the API surface as a single
   in-scope line, e.g. "The N API endpoints ... defined in the TDD").
   Also add one in_scope line per TDD capability flagged true in
   tdd_applicable_flags (concurrency control, resilience/fault
   handling, security/access control, kill-switch/rollout) -- do not
   add one that is false or absent.
2. out_of_scope must start from fdd_out_of_scope verbatim (paraphrase
   lightly for a testing audience, e.g. "defining X" instead of
   "configuration of X"), then add further exclusions ONLY if actually
   implied by the inputs: how upstream/external data is produced (if
   fdd_out_of_scope or business_objective mentions an external source),
   defining business rules/constraints themselves (if the FDD says they
   are pre-configured elsewhere), and any explicit "not allowed"
   behavior mentioned in the FDD (state that it is tested only to
   confirm it stays blocked, not exercised as a real path).
3. Do not invent an in-scope or out-of-scope item that has no basis in
   the payload. If the payload has nothing for a category, leave it out
   rather than padding the list.
4. Every in_scope and out_of_scope bullet is one line, no nested
   sub-bullets.

SELF-CHECK: for every out_of_scope bullet, could you point to the exact
input field it came from? If not, remove it.

Output strict JSON: in_scope (array of strings), out_of_scope (array of
strings), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section2 = fdd.get("2") or {}
    section4 = fdd.get("4") or {}
    endpoints = (tdd.get("5") or {}).get("endpoints") or []
    payload = {
        "fdd_in_scope": section2.get("in_scope"),
        "fdd_out_of_scope": section2.get("out_of_scope"),
        "persona_definition": section2.get("persona_definition"),
        "business_objective": section2.get("business_objective"),
        "fdd_requirements": [
            {"req_id": r.get("req_id"), "feature": r.get("feature")}
            for r in (section4.get("requirements") or [])
            if isinstance(r, dict)
        ],
        "tdd_endpoints": [
            {"route": e.get("route"), "description": e.get("description")}
            for e in endpoints
            if isinstance(e, dict)
        ],
        "tdd_applicable_flags": {
            "concurrency": (tdd.get("9") or {}).get("applicable"),
            "resilience": (tdd.get("11") or {}).get("applicable"),
            "security_relevant": bool(tdd.get("12")),
            "kill_switch": (tdd.get("15") or {}).get("applicable"),
        },
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    return merge_section(state, "2", "agent2_purpose_scope", result)
