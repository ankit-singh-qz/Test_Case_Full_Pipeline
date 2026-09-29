"""Shared helper every test_case agent uses to merge its output back into
state. Mirrors test_design_pipeline/agents/common.py's merge_section
exactly, but writes into test_case_sections instead of test_sections --
this pipeline expands scenarios into test cases, it does not generate new
scenarios, so the section id it merges into is the SAME section id its
source scenarios came from (e.g. agent11_positive_testing reads
test_design_sections["11"] and writes test_case_sections["11"]).

expand_test_cases() is the call every technique agent makes. The model
often marks a case blocked because a number or a schema was never
written down. That is not a pass/fail fork, so those cases are sent
back once and must come back as ready, with steps.
"""
import re

from llm import call_agent


# Appended to every technique agent's system prompt. The payload built in
# run() is the input; the JSON object returned by the model is the output.
# blocked_by_issue is a string or null -- never an array -- because
# assemble counts cases by that value as a dict key.
IO_SCHEMA = """

INPUT SCHEMA (the JSON user message):
{
  "scenarios": [
    {
      "scenario_id": string,
      "title": string,
      "src_refs": array,
      "design_technique": string,
      "level": string,
      "priority": "P1" | "P2" | "P3",
      "blocked_by_issue": string | null,
      "preconditions": array of string | string,
      "expected_result": string
    }
  ],
  "issues": [
    {
      "issue_id": string,
      "issue": string,
      "test_impact": string,
      "owner_hint": string,
      "related_sections": object
    }
  ] | null,
  "fields": [
    {
      "field_name": string,
      "rule": string,
      "valid_examples": array,
      "invalid_examples": array,
      "api_exposed": boolean
    }
  ] | null,
  "data_sets": [ { "data_set_id": string, "content": string } ] | null,
  "environment_needs": array of string | null
}

OUTPUT SCHEMA (your entire reply, JSON only):
{
  "test_cases": [
    {
      "test_case_id": string,
      "scenario_id": string,
      "title": string,
      "objective": string,
      "status": "ready" | "blocked",
      "blocked_by_issue": string | null,
      "reason": string | null,
      "preconditions": array of string | null,
      "steps": [
        {
          "step_no": number,
          "action": string,
          "test_data": string | null,
          "expected_result": string
        }
      ] | null,
      "overall_expected_result": string | null,
      "priority": "P1" | "P2" | "P3",
      "automatable": boolean | null
    }
  ],
  "assumptions_made": array of string
}

blocked_by_issue is a single string or null. If several issue ids apply,
join them into one string with ", " (example: "I-08, I-16"). Never return
an array for blocked_by_issue. On status "blocked", preconditions, steps,
overall_expected_result, and automatable are null; title and objective
are still strings. On status "ready", steps is a non-empty array.

status "blocked" is allowed only when the reason names two opposing
outcomes that would change pass/fail: the update is rejected or it is
applied; a partial write is rolled back or it is kept; a field is
required or it may be null. A missing number, missing maximum, missing
schema, or the word "undefined" is status "ready": write the steps, put
the assumption in reason and in assumptions_made, and still copy
blocked_by_issue. If the reason says the test can proceed, status is
"ready" and steps are filled in."""


# Appended to every technique agent's system prompt, right after
# IO_SCHEMA. This used to live inline in each prompt, which meant five of
# the ten agents -- Boundary, Error Handling, Security, Accessibility and
# Compatibility -- never got the "a missing number is not a behavioral
# question" half of it and blocked far more than the rest. Boundary alone
# accounted for twelve blocked cases in the captured run.
BLOCKED_OR_READY = """

BLOCKED VERSUS READY (applies to every scenario whose blocked_by_issue is
not null -- look the id up in `issues` and read its test_impact):

Block ONLY when the test's own PASS/FAIL criterion changes depending on
which of two real answers is correct. The giveaway is that you could
write both expected results and they contradict each other:
  - the write is rejected, or it is applied
  - the partial write is rolled back, or it is kept
  - the field is required, or it may be null
Then set status "blocked", copy blocked_by_issue from the scenario, set
reason to a tightened version of that test_impact, and leave
preconditions, steps, overall_expected_result and automatable null. title
and objective stay populated. Do not invent an answer the sources leave
open.

Do NOT block for a missing fact. A missing number (an SLA, threshold,
rate, or timing value), a missing maximum, a missing error code, a
missing SCHEMA or field list, or anything the source calls "undefined"
has exactly one sensible resolution: pick it, say so, and write the test.
Set status "ready", expand the steps normally, still copy
blocked_by_issue through for traceability, and state the assumption in
BOTH that test case's reason field AND this agent's assumptions_made
array -- for example "assuming a 5-minute SLA per FR-01, since no other
number is stated", or asserting only "rejected with a validation error"
where no specific code was ever given.

Two more things that are not grounds for blocking:
  - An issue about a subject this test does not touch. A contradiction
    about whether a write is persisted does not block a test that checks
    a message's wording, a field's length, or an encryption standard.
  - An issue the scenario cites for traceability while its own
    expected_result is already unambiguous.

LONG VALUES (every test case, every field): never write out a string
longer than 16 characters. A length boundary is a descriptor such as
"<string of 50 chars>" or "<string of 51 chars>", using the limit named
in the source. Do not count characters by typing them, and never use a
code-like expression such as "A".repeat(N). Short literals (a price, an
integer, an id already shorter than 16 characters) stay as the literal."""


def as_issue_string(value):
    """blocked_by_issue must be a string or None. Models sometimes emit a
    list of ids; join those so coverage counting can use the value as a
    dict key."""
    if value is None:
        return None
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def _normalize_result(result: dict) -> dict:
    if not isinstance(result, dict):
        return result
    cases = result.get("test_cases")
    if not isinstance(cases, list):
        return result
    normalized = []
    for case in cases:
        if not isinstance(case, dict):
            normalized.append(case)
            continue
        case = dict(case)
        if "blocked_by_issue" in case:
            case["blocked_by_issue"] = as_issue_string(case.get("blocked_by_issue"))
        normalized.append(case)
    result = dict(result)
    result["test_cases"] = normalized
    return result


# Word-boundary matches, so "applied" counts and "application" /
# "applicable" do not -- a bare "appl" substring turned any mention of an
# application into half a reject-versus-apply fork.
def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{word}", text) for word in words)


def _is_behavioral_fork(reason: str) -> bool:
    """True when two answers would make the same test pass or fail
    differently. A missing SLA, maximum, or schema is not this."""
    text = reason.lower()
    reject_or_apply = _has(text, "reject", "refus", "denied", "declin") and _has(
        text, "applied", "applies", "apply", "accept", "succeed", "persist"
    )
    rollback_or_keep = _has(text, "roll ?back", "rolled back", "undone", "revert") and _has(
        text, "commit", "kept", "keep", "retain", "persist"
    )
    required_or_null = _has(text, "null", "nullable", "optional", "absent") and _has(
        text, "required", "non-null", "populated", "mandatory"
    )
    persist_or_discard = _has(text, "persist", "stored", "saved", "written") and _has(
        text, "discard", "dropped", "lost", "not stored"
    )
    return (
        reject_or_apply or rollback_or_keep or required_or_null or persist_or_discard
    )


# A reason that says, in the model's own words, that the only thing
# missing is a fact. These are the cases worth rewriting into a real test.
_ABSENT_THING = (
    r"(?:maximum|minimum|upper bound|lower bound|bound|ceiling|schema|structure|"
    r"format|threshold|sla|limit|target|value|number|code|definition|contract)"
)
_MISSING_FACT_REASON = re.compile(
    r"not specified"
    r"|not defined"
    r"|not stated"
    r"|undefined"
    r"|unspecified"
    r"|never (?:stated|defined|specified|given)"
    # "no maximum", "no error code", "no pass/fail threshold is defined"
    rf"|\bno (?:[\w/-]+ ){{0,3}}{_ABSENT_THING}s?\b"
    rf"|\bmissing (?:[\w/-]+ ){{0,3}}{_ABSENT_THING}s?\b"
    rf"|\bno such {_ABSENT_THING}\b",
    re.IGNORECASE,
)


def _must_be_ready(case: dict) -> bool:
    """True when a blocked case should be sent back to be written properly.

    This used to default to True: anything whose reason did not literally
    contain one of the keyword pairs above was force-rewritten into a
    ready test. A genuine fork phrased differently -- "unclear whether the
    write is persisted or discarded" matched nothing -- was therefore
    turned into a passing-looking test with an invented expected result.
    A false block costs a line in the report; a false ready ships a wrong
    assertion, so the default is now to leave it blocked and only rewrite
    on a positive match."""
    if str(case.get("status") or "").lower() != "blocked":
        return False
    reason = str(case.get("reason") or "")
    lowered = reason.lower()

    # The model saying outright that nothing stops the test.
    if "can proceed" in lowered or "does not affect" in lowered:
        return True
    # An empty reason is not evidence of a fork.
    if not reason.strip():
        return True
    # A real fork outranks any missing-fact wording in the same sentence:
    # "rejected or applied, and no error code is stated" stays blocked.
    if _is_behavioral_fork(reason):
        return False
    return bool(_MISSING_FACT_REASON.search(reason))


def cases_that_must_be_ready(result: dict) -> list:
    """Blocked cases whose reason is a missing fact, or that admit the
    test can proceed. Real reject/apply, rollback/keep, and required/null
    forks are left blocked."""
    cases = result.get("test_cases") if isinstance(result, dict) else None
    if not isinstance(cases, list):
        return []
    flagged = []
    for case in cases:
        if not isinstance(case, dict) or not _must_be_ready(case):
            continue
        flagged.append(
            {
                "test_case_id": case.get("test_case_id"),
                "scenario_id": case.get("scenario_id"),
                "blocked_by_issue": case.get("blocked_by_issue"),
                "reason": case.get("reason"),
            }
        )
    return flagged


_REWRITE_INSTRUCTION = """

REWRITE (this request is a correction of your previous reply):
previous_test_cases is your last full list. rewrite_these_test_cases
lists the ones you blocked for a missing number, a missing maximum, a
missing schema, or an "undefined" fact, including any whose reason says
the test can proceed.

Return the FULL test_cases array, one entry per scenario, not only the
rewritten ones.
- For every id in rewrite_these_test_cases: set status "ready", fill
  preconditions, steps, and overall_expected_result, keep
  blocked_by_issue copied from the scenario, and state the assumption
  in that case's reason AND in assumptions_made.
- Leave a case blocked only when its reason names two opposing outcomes
  (rejected or applied; rolled back or kept; required or null). Do not
  change those cases.
- Never write out a string longer than 16 characters. A length
  boundary is a descriptor: "<string of N chars>".
JSON only."""


def _overlay_rewrites(original: dict, revised: dict, bad_ids: set) -> dict:
    """Keep the first reply, and replace only the cases that had to be
    rewritten. A second reply that returns just those cases still works."""
    revised_cases = {}
    for case in revised.get("test_cases") or []:
        if isinstance(case, dict) and case.get("test_case_id"):
            revised_cases[case["test_case_id"]] = case

    merged = []
    still_blocked = []
    for case in original.get("test_cases") or []:
        if not isinstance(case, dict):
            merged.append(case)
            continue
        case_id = case.get("test_case_id")
        if case_id in bad_ids and case_id in revised_cases:
            replacement = revised_cases[case_id]
            merged.append(replacement)
            if _must_be_ready(replacement):
                still_blocked.append(case_id)
        else:
            merged.append(case)

    assumptions = list(original.get("assumptions_made") or [])
    for assumption in revised.get("assumptions_made") or []:
        if assumption not in assumptions:
            assumptions.append(assumption)

    if still_blocked:
        print(
            "Still blocked after rewrite (left as returned): "
            + ", ".join(str(case_id) for case_id in still_blocked),
            flush=True,
        )

    out = dict(original)
    out["test_cases"] = merged
    out["assumptions_made"] = assumptions
    return out


def expand_test_cases(system_prompt: str, payload: dict) -> dict:
    """Call the model, then once more for any case blocked only because
    a fact was missing. One correction pass; a real pass/fail fork stays
    blocked."""
    result = _normalize_result(call_agent(system_prompt, payload))
    flagged = cases_that_must_be_ready(result)
    if not flagged:
        return result

    ids = [item["test_case_id"] for item in flagged]
    print(
        f"Rewriting {len(ids)} test cases blocked for a missing fact: "
        + ", ".join(str(case_id) for case_id in ids),
        flush=True,
    )
    retry_payload = dict(payload)
    retry_payload["previous_test_cases"] = result.get("test_cases")
    retry_payload["rewrite_these_test_cases"] = flagged
    revised = _normalize_result(
        call_agent(system_prompt + _REWRITE_INSTRUCTION, retry_payload)
    )
    return _overlay_rewrites(result, revised, set(ids))


def merge_section(state: dict, section_id: str, agent_name: str, result: dict) -> dict:
    result = _normalize_result(result)
    sections = dict(state.get("test_case_sections", {}))
    sections[section_id] = result

    pool = list(state.get("assumptions_pool", []))
    for assumption in result.get("assumptions_made", []) or []:
        pool.append({"source_agent": agent_name, "assumption": assumption})

    return {"test_case_sections": sections, "assumptions_pool": pool}
