"""Section 18 -- Usability Testing (USAB) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Usability Testing (USAB) scenarios: ease of use, clarity, and
navigation. This feature may be a backend/API capability with no
end-user screen -- if so, do not force UI-style scenarios (no "the screen
is easy to navigate"); instead scope usability to the API CONSUMER/
OPERATOR experience: error message clarity, response self-
descriptiveness, and whether the persona can act on what they are told.

RULES:
1. First decide applicable: set it to true if EITHER has_ui_signal is
   true, OR fdd_error_matrix contains at least one user_facing_behavior
   entry (this means a human consumes the output even without a
   graphical screen). Set to false only if neither is present, and
   explain why in decisions_made.
2. If applicable and has_ui_signal is false: scope every scenario to
   the operator/API-consumer angle only. One scenario per distinct
   user_facing_behavior entry, verifying the message states what
   happened, why, and (if applicable) what the persona should do next
   -- flag any entry that is vague (does not say what to do next) as
   its own scenario, with expected_result describing what clarity is
   missing, rather than skipping it.
3. If applicable and has_ui_signal is true, additionally write general
   navigation/clarity scenarios appropriate to persona_definition.
4. If tdd_error_message_fields shows the API returns a structured
   message (not just a raw code), write one scenario confirming the
   message text itself (not just the HTTP code) is descriptive.
5. design_technique is "Inspection" for every scenario in this section.
6. priority is P3 unless a message describes a financial/compliance-
   critical action, in which case P2.
7. level: "Usability".
8. scenario_id format: USAB-01, USAB-02, ...

Output strict JSON: applicable (boolean), scenarios (array of
{scenario_id, title, src_refs, design_technique, level, priority,
blocked_by_issue, preconditions, expected_result}), decisions_made
(array), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section2 = fdd.get("2") or {}
    section9 = fdd.get("9") or {}
    tdd5 = (state.get("tdd_sections") or {}).get("5") or {}
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    error_message_fields = []
    for e in tdd5.get("endpoints") or []:
        if isinstance(e, dict):
            for err in e.get("error_responses") or []:
                if isinstance(err, dict) and err.get("message"):
                    error_message_fields.append(err.get("message"))
    payload = {
        "has_ui_signal": state.get("has_ui_signal", False),
        "persona_definition": section2.get("persona_definition"),
        "fdd_error_matrix": section9.get("error_matrix"),
        "tdd_error_message_fields": error_message_fields,
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "18", "agent18_usability_testing", result)
