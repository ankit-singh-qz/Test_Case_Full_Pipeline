"""Section 9 -- Entry, Exit & Suspension Criteria. Tier 4."""
from llm import call_agent
from agents.common import (
    CHAR_LIMIT_RULE,
    fix_open_issue_count,
    merge_section,
    substitute_placeholders,
)

SCENARIO_SECTION_IDS = ["11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]


def _count_priorities(test_sections: dict) -> dict:
    counts = {"P1": 0, "P2": 0, "P3": 0}
    for sid in SCENARIO_SECTION_IDS:
        for scenario in (test_sections.get(sid) or {}).get("scenarios") or []:
            if isinstance(scenario, dict):
                priority = scenario.get("priority", "P2")
                counts[priority] = counts.get(priority, 0) + 1
    return counts


SYSTEM_PROMPT = """You define entry, exit, and suspension criteria for test execution, using
the strategy's priority rubric and the actual scenario counts generated.

RULES:
1. entry_criteria must include: unresolved-issues gating (only if
   open_issue_count > 0 -- write the literal placeholder text
   {OPEN_ISSUE_COUNT} where the count belongs, do not type the number
   yourself), environment/stub readiness (generic, always include), and
   a rollout/kill-switch readiness item only if tdd_deployment_relevant
   is true.
2. exit_criteria must include: "100% of all {P1_COUNT} P1 scenarios
   executed and passed" (write that placeholder literally, do not type
   the number), a P2 pass-rate threshold on all {P2_COUNT} P2 scenarios
   (state a percentage, e.g. 95%, as a standard default since the
   inputs do not specify one -- say so in assumptions_made; the
   percentage itself is fine to type, only the scenario counts use
   placeholders), a requirement that every FR/AC has at least one
   passing scenario (reference that this is validated via the
   traceability matrix, without re-deriving it here), and a
   kill-switch/rollout verification item only if tdd_deployment_relevant
   is true.
3. suspension_criteria must include environment/stub unavailability and
   any partial-state defect class implied by p1_escalation_notes (e.g.
   "a change applied without its required companion record" if an
   escalation note describes exactly that kind of risk) -- do not
   invent a suspension trigger with no basis in p1_escalation_notes or
   fdd_tier.
4. {P1_COUNT}, {P2_COUNT}, and {OPEN_ISSUE_COUNT} are the ONLY three
   placeholder tokens available. Write them exactly as shown, in that
   exact bracketed form, wherever one of those three counts belongs in
   a sentence -- a separate deterministic step substitutes the real
   number afterward. Never type a digit yourself for any of these three
   counts, and never invent a placeholder name that isn't one of these
   three.

Output strict JSON: entry_criteria (array), exit_criteria (array),
suspension_criteria (array), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    tdd_included = set(state.get("tdd_included_sections") or [])
    test_sections = state.get("test_sections") or {}
    test4 = test_sections.get("4") or {}
    test5 = test_sections.get("5") or {}
    open_issue_count = len(test4.get("issues") or [])
    priority_counts = _count_priorities(test_sections)
    payload = {
        "fdd_tier": state.get("fdd_tier"),
        "open_issue_count": open_issue_count,
        "p1_escalation_notes": test5.get("p1_escalation_notes"),
        "priority_counts": priority_counts,
        "tdd_deployment_relevant": "14" in tdd_included or "15" in tdd_included,
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    keys = ["entry_criteria", "exit_criteria", "suspension_criteria", "assumptions_made"]
    result = substitute_placeholders(
        result,
        {
            "{P1_COUNT}": priority_counts.get("P1", 0),
            "{P2_COUNT}": priority_counts.get("P2", 0),
            "{OPEN_ISSUE_COUNT}": open_issue_count,
        },
        keys,
    )
    result = fix_open_issue_count(result, open_issue_count, keys)
    return merge_section(state, "9", "agent9_entry_exit_criteria", result)
