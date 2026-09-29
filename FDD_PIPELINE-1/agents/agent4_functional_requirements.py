"""Section 4 -- Functional Requirements. Tier 2 (parallel with Agent 3)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT =""" Extract functional requirements from the story, in_scope, and
acceptance criteria. Honor out_of_scope.

RULES:
1. One requirement = one action, one verb. If a sentence needs "and"
   between two verbs, split it into two requirements. This rule
   ALWAYS applies, including to a validate-then-notify pair (e.g.
   "validate X and display an error message") -- validation and
   user notification are two different actions even when they
   always happen together. Rule 8 below does not override this.
2. req_id: FR-01, FR-02, ... two digits, sequential. No other format.
3. Cover only in_scope / explicit story capabilities. Never cover
   out_of_scope.
4. feature: the main business capability this FR belongs to, as a
   short noun phrase taken from the story (e.g. "dynamic pricing",
   "seat management", "audit logging"). Reuse the same feature name
   for FRs that implement the same capability. Do not put a system
   actor, service, or layer here.
5. shall_statement: one sentence starting with "The system shall..."
   or "The <persona> shall...".
6. ui_copy_or_message: null unless a person reads that text on a
   screen. Do not invent backend status messages.
7. Use only numbers that appear in the story. Never invent a SLA,
   count, or threshold (no "1 minute" if the story says "5 minutes").
8. Normal size is 4-6 requirements. Rule 8 governs INTERNAL
   ARCHITECTURE steps only (detect / calculate / persist / notify a
   downstream SYSTEM) -- do not split a capability into those
   internal steps unless the story names them separately. Rule 8
   does NOT apply to splitting a validation from its user-facing
   error message (that's still governed by Rule 1) or to any other
   pair of actions a real user or the story's acceptance criteria
   distinguish.
9. Do not add a requirement the story has no basis for. "So that"
   outcomes are assumptions, not FRs.
10. Trigger vs automation: if the story says a persona "wants to
    update" without saying the system auto-detects, do not add a
    "detect change and trigger" FR. If acceptance criteria say the
    system updates within N minutes of a metric change, that SLA is
    an FR on the system, not a new detection subsystem.

SELF-CHECK, in this order:
(a) Does any shall_statement contain "and" joining two verbs? If yes,
    split it -- this check always wins over Rule 8, with one
    exception: don't split if the two verbs describe the same
    internal architecture step the story never named separately
    (e.g. "detect and trigger" for one auto-updating capability).
(b) Every FR has a feature.
(c) No invented layers or numbers.
(d) ui_copy_or_message is null for every non-UI requirement.
(e) Every FR traces to in_scope or an acceptance criterion.

Output strict JSON: requirements (array of {req_id, feature,
shall_statement, ui_copy_or_message}), assumptions_made (array).
JSON only."""


def run(state: dict) -> dict:
    section2 = state.get("sections", {}).get("2", {})
    payload = {
        "raw_user_story": state["raw_user_story"],
        "parsed_clauses": section2.get("parsed_clauses"),
        "in_scope": section2.get("in_scope"),
        "out_of_scope": section2.get("out_of_scope"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "4", "agent4_functional_requirements", result)