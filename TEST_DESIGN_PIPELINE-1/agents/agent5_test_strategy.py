"""Section 5 -- Test Strategy. Tier 2 (uses Agent 4's own-run output).

Its output (design_techniques vocabulary + prioritization_rules) is read
by all ten Tier 3 technique agents, so consistency matters more here than
in most sections -- every scenario downstream must trace its technique
label and priority back to what this agent defines."""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You define the test strategy: levels, design-technique catalog, and
priority rubric that every downstream scenario-generating agent must use
consistently.

RULES:
1. test_levels: only include a level actually supported by what applies
   this run. Always include Unit/Component, Integration, API, and
   End-to-end. Include Performance only if fdd_tier is medium/large or
   tdd_performance_relevant is true. Include Security only if
   tdd_security_present is true. Include Deployment only if
   tdd_deployment_relevant is true.
2. design_techniques: a fixed catalog, one row per technique actually
   usable given what is present -- pick from exactly this vocabulary
   and no others: "Equivalence Partitioning", "Boundary Value
   Analysis", "Decision Table", "State Transition", "Fault Injection",
   "Concurrency/Race Testing", "Error Guessing", "Inspection". For
   each, name concretely what it will be applied to in THIS feature
   (not a generic textbook definition).
3. prioritization_rules: state the P1/P2/P3 definitions using the
   standard rubric (P1 = core requirement or data-integrity/security/
   financial risk, must pass before release; P2 = important behavior
   or resilience, failure has a workaround; P3 = low-risk/cosmetic/
   observability) -- then separately populate p1_escalation_notes with
   any case from THIS run's issues list that should force something to
   P1 (e.g. if an issue describes a design where one dependency's
   failure blocks an entire capability, or where a failure could leave
   data partially applied). Only add an escalation note tied to a
   specific issue_id from issues; do not invent one.
4. Do not describe a technique or level that has no basis in
   tdd_performance_relevant / tdd_security_present /
   tdd_deployment_relevant / tdd_concurrency_present /
   tdd_resilience_present / fdd_tier -- an absent capability gets no
   row.

Output strict JSON: test_levels (array of {level_code, focus}),
design_techniques (array of {technique, applied_to}),
prioritization_rules (array of {priority, definition}),
p1_escalation_notes (array of {issue_id, note}), assumptions_made
(array). JSON only."""


def run(state: dict) -> dict:
    tdd_included = set(state.get("tdd_included_sections") or [])
    test4 = (state.get("test_sections") or {}).get("4") or {}
    payload = {
        "fdd_tier": state.get("fdd_tier"),
        "tdd_performance_relevant": "3" in tdd_included or "13" in tdd_included,
        "tdd_security_present": "12" in tdd_included,
        "tdd_deployment_relevant": "14" in tdd_included or "15" in tdd_included,
        "tdd_concurrency_present": "9" in tdd_included,
        "tdd_resilience_present": "11" in tdd_included,
        "issues": test4.get("issues"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    return merge_section(state, "5", "agent5_test_strategy", result)
