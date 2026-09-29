"""Section 19 -- Accessibility Testing (ACC) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Accessibility Testing (ACC) scenarios: accessibility for users
with disabilities and assistive technologies. This only applies when a
real end-user UI surface exists -- a backend/API-only feature with no UI
has no accessibility surface to test.

RULES:
1. applicable is true ONLY if has_ui_signal is true OR
   fdd_accessibility_notes is non-empty. Otherwise false.
2. If false, decisions_made must state plainly: no UI surface is
   evidenced in the FDD/TDD for this feature, so accessibility testing
   is deferred pending confirmation a UI exists; do not guess at
   scenarios for a UI that may not exist.
3. If true, write one scenario per distinct item in
   fdd_accessibility_notes (if any), plus baseline scenarios only
   insofar as persona_definition or fdd_accessibility_notes gives a
   concrete basis for them (keyboard navigation, screen-reader labels,
   color-contrast/color-only signaling, focus order) -- do not invent a
   scenario with no textual anchor in the input.
4. design_technique is "Inspection" for every scenario here.
5. priority: P2 by default, P1 only if fdd_accessibility_notes
   explicitly ties accessibility to a compliance/legal requirement.
6. level: "Usability".
7. scenario_id format: ACC-01, ACC-02, ...

Output strict JSON: applicable (boolean), scenarios (array of
{scenario_id, title, src_refs, design_technique, level, priority,
blocked_by_issue, preconditions, expected_result}), decisions_made
(array), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section2 = fdd.get("2") or {}
    section10 = fdd.get("10") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "has_ui_signal": state.get("has_ui_signal", False),
        "persona_definition": section2.get("persona_definition"),
        "fdd_accessibility_notes": section10.get("accessibility_notes"),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "19", "agent19_accessibility_testing", result)
