"""Section 3 -- Test Basis. Tier 2 (uses Agent 2's own-run output)."""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You produce a source-to-purpose cross-reference table: which FDD/TDD
sections feed which category of test condition. This is a structural
mapping, not a content summary -- you are told WHICH sections exist and
applied for this run, and you state what kind of testing each one
justifies.

RULES:
1. Only list an FDD/TDD section as a basis row if fdd_sections_present
   or tdd_included_sections confirms it actually ran for this document
   (do not include a section id that is absent or marked not
   applicable/triggered:false).
2. used_for must name the actual test category the section feeds, from
   this vocabulary: "Functional test conditions", "Negative/exception
   scenarios", "Field validation, boundary values", "Acceptance-level
   tests", "Performance test planning", "Concurrency/race test
   planning", "API/integration tests", "Security and access-control
   tests", "Resilience/fault-injection tests", "Deployment/kill-switch
   tests", "Observability/logging tests" -- combine two categories in
   one row only if that section genuinely feeds both (state both,
   comma separated).
3. Group consecutive FDD or TDD sections into one row only if they feed
   the exact same used_for category (e.g. "TDD sections 9, 11" if both
   feed concurrency/resilience planning) -- do not force a group that
   mixes categories.
4. Reference in_scope (Agent 2's output) only to decide whether a
   section's content is worth citing at all -- do not copy scope
   bullets into this table.

Output strict JSON: basis (array of {source, used_for}), assumptions_made
(array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd_included = state.get("tdd_included_sections") or []
    test2 = (state.get("test_sections") or {}).get("2") or {}

    def _present(section_id: str) -> bool:
        data = fdd.get(section_id)
        if data is None:
            return False
        return data.get("triggered") is not False

    payload = {
        "fdd_tier": state.get("fdd_tier"),
        "fdd_sections_present": [
            sid for sid in [str(i) for i in range(1, 14)] if _present(sid)
        ],
        "tdd_included_sections": tdd_included,
        "in_scope": test2.get("in_scope"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    return merge_section(state, "3", "agent3_test_basis", result)
