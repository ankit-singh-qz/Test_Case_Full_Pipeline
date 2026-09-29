"""Section 10 -- Next Steps. Tier 5, solo, always last -- fan-in reviewer
reading Agent 8 and Agent 9's finished output (same role as
fdd_pipeline's Agent 8 / tdd_pipeline's Agent 16: read what everything
else concluded, don't invent from scratch)."""
from llm import call_agent
from agents.common import (
    CHAR_LIMIT_RULE,
    fix_open_issue_count,
    merge_section,
    substitute_placeholders,
)

SYSTEM_PROMPT = """You write the closing action list for this Test Case Design Document,
grounded in what the traceability matrix and exit criteria actually
found -- not a generic template.

RULES:
1. If coverage_gaps is non-empty, the first next-step must be to close
   those specific gaps (name them, do not say "review coverage"
   vaguely).
2. If open_issue_count > 0, a next step must be to resolve the issues
   log before detailed test cases are finalized for any scenario with a
   non-null blocked_by_issue. Write the literal placeholder text
   {OPEN_ISSUE_COUNT} where that count belongs (e.g. "resolve all
   {OPEN_ISSUE_COUNT} open issues") -- do not type a digit yourself. A
   deterministic step substitutes the real number afterward. Never
   compute, estimate, or quote a different count by counting issue ids
   that happen to appear elsewhere in this payload (e.g. inside
   coverage_gaps text) -- those lists are illustrative, not exhaustive.
3. Do not state a specific numeric threshold, percentage, count, or
   load size (e.g. a latency target in ms, "100+ concurrent updates", a
   pass-rate percentage, a scenario count) unless that exact
   number/percentage already appears verbatim as plain text in
   coverage_gaps or exit_criteria -- if so, you may quote it exactly as
   written there. If a next step needs a threshold that is not yet
   defined anywhere in the inputs, say the threshold still needs to be
   defined (during issue resolution) -- do not propose your own number
   to fill the gap, and never retype a number from exit_criteria from
   memory -- copy it exactly as it appears there.
4. Always include, in this order after the above: expand each scenario
   into detailed step-by-step test cases with concrete data and
   expected results, build the environment/stubs and seed data, decide
   what to automate vs. test manually (favor automating API/boundary/
   regression scenarios), execute and track against the traceability
   matrix.
5. Keep each step to one sentence. Do not repeat a step already implied
   by an earlier one.

SELF-CHECK: does any step contain a number (a count, percentage, or
threshold) that is not the {OPEN_ISSUE_COUNT} placeholder and does not
appear verbatim in coverage_gaps or exit_criteria? If so, remove that
invented or misremembered number and rephrase the step without it.

Output strict JSON: next_steps (array of strings), assumptions_made
(array). JSON only."""


def run(state: dict) -> dict:
    test_sections = state.get("test_sections") or {}
    test4 = test_sections.get("4") or {}
    test8 = test_sections.get("8") or {}
    test9 = test_sections.get("9") or {}
    open_issue_count = len(test4.get("issues") or [])
    payload = {
        "coverage_gaps": test8.get("coverage_gaps"),
        "open_issue_count": open_issue_count,
        "exit_criteria": test9.get("exit_criteria"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    keys = ["next_steps", "assumptions_made"]
    result = substitute_placeholders(result, {"{OPEN_ISSUE_COUNT}": open_issue_count}, keys)
    result = fix_open_issue_count(result, open_issue_count, keys)
    return merge_section(state, "10", "agent10_next_steps", result)
