"""Section 4 -- Issues in Source Documents. Tier 1, always runs.

Cross-checks the FDD and TDD for written contradictions that would
change whether a test passes or fails. A missing maximum, a missing
schema, or a risk recommendation is not an issue. Reuses the TDD's own Agent 16 conflicts[] as a seed
rather than re-deriving them from scratch, then looks for additional
issues Agent 16 could not see (it only compares TDD sections against each
other; this agent also compares against the FDD). This is deliberately
the broadest-reading agent in this pipeline -- every other agent reads a
narrow slice of one or two sections; this one's entire job is finding
contradictions across both documents.

Every issue here becomes a blocked_by_issue reference on downstream
scenarios, and from there a blocked test case. An issue that is really
just a missing number therefore costs a whole branch of the test pack, so
the prompt's rules are also enforced in Python: an issue survives only if
it carries two quoted statements that actually disagree. See
_enforce_two_sided.
"""
import re

from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You audit an FDD and TDD pair for contradictions that would
change whether a test passes or fails. You do not write test cases --
you produce an issues log that downstream test-design agents use to mark
specific scenarios BLOCKED or CLARIFY via a blocked_by_issue reference.

An issue exists only when two written statements disagree about the
outcome. A missing detail that the source already calls unspecified, or
a risk note that recommends something the requirements never required,
is not an issue.

RULES:
1. Read tdd_conflicts first (the TDD's own Agent 16 output). Each one is
   a candidate, not an automatic issue: keep it only if it also passes
   rule 2 and you can quote both sides of it from the inputs. Give each
   surviving issue a sequential issue_id (I-01, I-02, ...). If a later
   finding is the same disagreement, merge it into that issue instead of
   adding another id.
2. Then look across the fdd_* and tdd_* inputs for disagreements Agent 16
   could not see, because it never reads the FDD directly. Report one
   only when both sides are written down and they pick different outcomes:
   a. A constraint disagrees: required versus nullable under the same
      condition, or a type or precision that cannot both be true. The
      same precision written in words and in a column type is not a
      disagreement.
   b. An operation's outcome disagrees: one statement says it is
      rejected or held, and another says it is applied.
   c. An in-progress operation disagrees: one statement says it is
      rejected before it is stored, and another says a partial result
      is kept or must be undone.
   d. A named concurrency mechanism has no conflict error defined.
      One issue for that missing code, not one issue per operation.
   e. Two stated numeric limits cannot both be met (a deadline shorter
      than the worst case of the retry or timeout schedule that is
      supposed to satisfy it) -- AND ONLY when both numbers describe the
      same operation at the same scope. A mechanism scoped to one named
      failure scenario (check its own fdd_scenario / rationale text) is
      a sub-step, not a restatement of an end-to-end requirement, even
      when its rationale mentions the requirement's number. If the
      mechanism's own rationale cites the other number without disputing
      it, that is cross-referencing, not disagreement -- do not report it.
3. Do not report any of the following:
   a. A bound, rate, or size the source already says is not specified.
      Do not invent a ceiling from the domain. A stated lower bound or
      a column type is enough for the tests that can be written.
   b. A field whose structure the source says is not specified,
      including values owned by another system. A test can assume a
      minimal value that satisfies the constraints that are written.
   c. A qualitative word (such as immediate or real-time) when a number
      for that same behavior is already stated. Use the number. A risk
      note that warns about a bad outcome is not a second limit.
   d. A risk or a recommendation that asks for a control, an endpoint,
      or a scope the requirements never required. Absence of something
      that was only suggested is not a disagreement.
   e. How a derived or previous value is produced when both documents
      describe the same meaning for it.
   f. The same pair of outcomes written in two places. Keep one issue.
   g. Anything tdd_decisions already records. Each entry there is a gap
      the TDD noticed (why_not_derivable) and closed on purpose
      (chosen). A deliberate choice is not a disagreement. It becomes
      one only if some other statement picks the opposite outcome, and
      then the issue is that disagreement, not the gap.
   h. A document's own commentary about ambiguity in ITS OWN qualitative
      term (a risk note wondering how "real-time" might be interpreted,
      for instance), when the other document is simply silent on that
      behavior. One document hedging about itself, with nothing on the
      other side to disagree with it, is not two statements picking
      different outcomes -- it is still just one document being vague.
4. evidence is how you prove rule 2. statement_a and statement_b are two
   short quotes, copied word for word from the payload, that pick
   DIFFERENT outcomes for the same situation. Do not paraphrase them, do
   not quote the same side twice, and do not quote something the payload
   does not contain. An issue with only one real quote is not an issue --
   delete it instead of inventing a second quote.
5. test_impact must name the two outcomes that would make the test pass
   or fail differently, in the form "X, or Y". Never write that a test
   "cannot be defined", "cannot be finalized", "cannot be written",
   "cannot be determined", or "is blocked" -- those phrases describe a
   missing number or a missing structure, which rule 3 already excludes.
6. owner_hint is a short role pair (e.g. "BA/Dev", "Dev", "Architect",
   "PM/Stakeholders", "BA/Business owner").
7. related_sections lists which fdd/tdd section numbers the issue spans,
   e.g. {"fdd": ["6"], "tdd": ["4"]}. Use ONLY the section numbers given
   in section_map, which says which section each payload key came from.
   Never guess a section number and never use a row's position in a list
   as one.

SELF-CHECK: for every issue, re-read evidence.statement_a and
evidence.statement_b. Do they appear verbatim in the payload, and do they
pick opposite outcomes? If either answer is no, delete the issue. If two
issues describe the same pair of outcomes, keep one.

Output strict JSON: issues (array of {issue_id, issue, test_impact,
evidence: {statement_a, statement_b}, owner_hint, related_sections}),
assumptions_made (array). JSON only."""


# Which section each payload key was read from. Sent to the model so
# related_sections can be filled from fact rather than guessed -- without
# it, the model has been observed to emit a field's row index ("fdd": "7")
# in place of the section it came from.
SECTION_MAP = {
    "fdd_requirements": {"fdd": "4"},
    "fdd_exception_paths": {"fdd": "5"},
    "fdd_fields": {"fdd": "6"},
    "fdd_risks": {"fdd": "8"},
    "fdd_implied_gaps": {"fdd": "8"},
    "fdd_error_matrix": {"fdd": "9"},
    "fdd_performance_target": {"fdd": "12"},
    "fdd_concurrency_note": {"fdd": "12"},
    "fdd_migration_notes": {"fdd": "13"},
    "fdd_kill_switch_note": {"fdd": "13"},
    "tdd_columns": {"tdd": "4"},
    "tdd_table_name": {"tdd": "4"},
    "tdd_existing_table_name": {"tdd": "4"},
    "tdd_endpoints": {"tdd": "5"},
    "tdd_lock_strategy": {"tdd": "9"},
    "tdd_concurrency_notes": {"tdd": "9"},
    "tdd_resilience_mechanisms": {"tdd": "11"},
    "tdd_authn_authz": {"tdd": "12"},
    "tdd_token_scopes": {"tdd": "12"},
    "tdd_kill_switch": {"tdd": "15"},
    "tdd_decisions": {"tdd": "16"},
    "tdd_conflicts": {"tdd": "16"},
}

# TDD Agent 16 logs every "the FDD didn't specify X, so we chose Y"
# decision. Those are the exact gaps this agent keeps mistaking for
# contradictions, so it needs to see that they were decided on purpose.
# Only the sections this agent already reads are worth the tokens.
DECISION_SECTIONS = {"4", "5", "9", "11", "12", "15"}

# An issue is only worth a downstream block if both sides are real. A
# one-word "quote" is not.
MIN_EVIDENCE_CHARS = 20

# Phrases that describe a missing fact rather than a disagreement. Rule 5
# forbids them; this catches the reply that wrote one anyway. Matching on
# these alone, rather than also looking for two outcomes in the same
# sentence, is deliberate: "cannot be finalized ... will fail or be
# blocked" satisfies any "is there an 'or'?" test while still describing a
# gap rather than a fork. A genuine fork restated as "X, or Y" on the
# rewrite pass gets back in.
_MISSING_FACT_IMPACT = re.compile(
    r"cannot be (defined|finalized|finalised|written|determined|established|"
    r"specified|validated)"
    r"|can(?:not|'t) (?:be )?determine"
    r"|(?:are|is) blocked"
    r"|no (?:pass/fail|pass-fail) criteri",
    re.IGNORECASE,
)


def _clean(value) -> str:
    return str(value or "").strip()


def _evidence_pair(issue: dict) -> tuple:
    evidence = issue.get("evidence")
    if not isinstance(evidence, dict):
        return "", ""
    return _clean(evidence.get("statement_a")), _clean(evidence.get("statement_b"))


def _rejection_reason(issue: dict) -> str:
    """Why this issue is not worth blocking a test over, or "" to keep it."""
    if not isinstance(issue, dict):
        return "not an object"

    statement_a, statement_b = _evidence_pair(issue)
    if len(statement_a) < MIN_EVIDENCE_CHARS or len(statement_b) < MIN_EVIDENCE_CHARS:
        return (
            "evidence needs two quoted statements of at least "
            f"{MIN_EVIDENCE_CHARS} characters each; one side is missing or too short"
        )
    if statement_a.lower() == statement_b.lower():
        return "evidence quotes the same statement twice, so nothing disagrees"

    impact = _clean(issue.get("test_impact"))
    if not impact:
        return "test_impact is empty, so the pass/fail fork is unnamed"
    if _MISSING_FACT_IMPACT.search(impact):
        return (
            "test_impact describes a missing fact rather than two outcomes; "
            'restate it as "X, or Y" naming the two results that would make '
            "the test pass or fail differently"
        )
    return ""


def _dedupe_key(issue: dict) -> tuple:
    statement_a, statement_b = _evidence_pair(issue)
    pair = sorted([statement_a.lower(), statement_b.lower()])
    return tuple(pair)


def _renumber(issues: list) -> list:
    renumbered = []
    for index, issue in enumerate(issues, start=1):
        issue = dict(issue)
        issue["issue_id"] = f"I-{index:02d}"
        renumbered.append(issue)
    return renumbered


def _enforce_two_sided(result: dict) -> tuple:
    """Keep only issues that quote two statements which actually disagree.

    Returns (filtered_result, rejected) where rejected carries the reason
    each dropped issue failed, so the rewrite pass can hand them back.
    Survivors are deduplicated on their evidence pair and renumbered
    I-01..I-NN, because a model that merges two findings tends to leave a
    hole in the sequence."""
    issues = result.get("issues") if isinstance(result, dict) else None
    if not isinstance(issues, list):
        return result, []

    kept = []
    rejected = []
    seen = {}
    for issue in issues:
        reason = _rejection_reason(issue)
        if reason:
            rejected.append(
                {
                    "issue_id": issue.get("issue_id") if isinstance(issue, dict) else None,
                    "issue": issue.get("issue") if isinstance(issue, dict) else str(issue),
                    "why_rejected": reason,
                }
            )
            continue
        key = _dedupe_key(issue)
        if key in seen:
            rejected.append(
                {
                    "issue_id": issue.get("issue_id"),
                    "issue": issue.get("issue"),
                    "why_rejected": (
                        "duplicate of "
                        f"{seen[key]} -- the same pair of outcomes, already kept once"
                    ),
                }
            )
            continue
        seen[key] = issue.get("issue_id")
        kept.append(issue)

    out = dict(result)
    out["issues"] = _renumber(kept)
    return out, rejected


_REWRITE_INSTRUCTION = """

REWRITE (this request is a correction of your previous reply):
rejected_issues lists findings from your last reply that were thrown out,
each with why_rejected. Everything else you wrote was accepted.

Return ONLY the issues that belong in the log after this correction --
the ones you can now prove, not the ones already accepted.
- Bring a rejected finding back only if you can quote two statements,
  word for word from the payload, that pick different outcomes for the
  same situation, and write test_impact as "X, or Y".
- If a rejected finding is really a missing number, a missing maximum, a
  missing schema, or something the source already calls unspecified,
  leave it out. Rule 3 excludes it. Saying so in assumptions_made is
  enough.
- Do not restate a finding that was accepted, and do not renumber
  anything -- issue_id is reassigned afterwards.
If nothing can be proven, return an empty issues array.
JSON only."""


def _merge_rewrite(original: dict, revised: dict) -> dict:
    """Append whatever the rewrite pass could prove to what already
    survived, then dedupe and renumber the combined log once."""
    combined = list(original.get("issues") or [])
    combined.extend(
        issue for issue in (revised.get("issues") or []) if isinstance(issue, dict)
    )

    merged = dict(original)
    merged["issues"] = combined
    merged, rejected_again = _enforce_two_sided(merged)

    assumptions = list(original.get("assumptions_made") or [])
    for assumption in revised.get("assumptions_made") or []:
        if assumption not in assumptions:
            assumptions.append(assumption)
    merged["assumptions_made"] = assumptions

    if rejected_again:
        print(
            f"Rewrite pass returned {len(rejected_again)} issues that still "
            "had no two-sided evidence; dropped.",
            flush=True,
        )
    return merged


def audit_issues(payload: dict) -> dict:
    """Call the model, drop every one-sided finding, and give those one
    chance to come back proven. Anything that cannot quote both sides
    twice in a row is not an issue."""
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    result, rejected = _enforce_two_sided(result)
    if not rejected:
        return result

    print(
        f"Dropped {len(rejected)} issues without two-sided evidence: "
        + ", ".join(str(item.get("issue_id")) for item in rejected),
        flush=True,
    )
    retry_payload = dict(payload)
    retry_payload["rejected_issues"] = rejected
    revised = call_agent(
        SYSTEM_PROMPT + CHAR_LIMIT_RULE + _REWRITE_INSTRUCTION, retry_payload
    )
    merged = _merge_rewrite(result, revised)
    print(f"Issues log settled at {len(merged.get('issues') or [])}.", flush=True)
    return merged


def _relevant_decisions(tdd16: dict) -> list:
    """Agent 16's decisions for the sections this agent reads, trimmed to
    the two fields that matter here: what the source left open, and what
    was chosen anyway."""
    decisions = []
    for decision in tdd16.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        if str(decision.get("source_section") or "") not in DECISION_SECTIONS:
            continue
        decisions.append(
            {
                "decision": decision.get("decision"),
                "why_not_derivable": decision.get("why_not_derivable"),
                "chosen": decision.get("chosen"),
                "source_section": decision.get("source_section"),
            }
        )
    return decisions


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section4 = fdd.get("4") or {}
    section5 = fdd.get("5") or {}
    section6 = fdd.get("6") or {}
    section8 = fdd.get("8") or {}
    section9 = fdd.get("9") or {}
    section12 = fdd.get("12") or {}
    section13 = fdd.get("13") or {}
    tdd4 = tdd.get("4") or {}
    tdd5 = tdd.get("5") or {}
    tdd9 = tdd.get("9") or {}
    tdd11 = tdd.get("11") or {}
    tdd12 = tdd.get("12") or {}
    tdd15 = tdd.get("15") or {}
    tdd16 = tdd.get("16") or {}
    payload = {
        "section_map": SECTION_MAP,
        "fdd_requirements": section4.get("requirements"),
        "fdd_exception_paths": section5.get("exception_paths"),
        "fdd_fields": section6.get("fields"),
        "fdd_risks": section8.get("risks"),
        "fdd_implied_gaps": section8.get("implied_gaps"),
        "fdd_error_matrix": section9.get("error_matrix"),
        "fdd_performance_target": section12.get("performance_target"),
        "fdd_concurrency_note": section12.get("concurrency_note"),
        "fdd_migration_notes": section13.get("migration_notes"),
        "fdd_kill_switch_note": section13.get("kill_switch_note"),
        "tdd_columns": tdd4.get("columns"),
        "tdd_table_name": tdd4.get("table_name"),
        "tdd_existing_table_name": tdd4.get("existing_table_name"),
        "tdd_endpoints": tdd5.get("endpoints"),
        "tdd_lock_strategy": tdd9.get("lock_strategy"),
        "tdd_concurrency_notes": tdd9.get("reconciliation_notes"),
        "tdd_resilience_mechanisms": tdd11.get("mechanisms"),
        "tdd_authn_authz": tdd12.get("authn_authz"),
        "tdd_token_scopes": tdd12.get("token_scopes"),
        "tdd_kill_switch": tdd15,
        "tdd_decisions": _relevant_decisions(tdd16),
        "tdd_conflicts": tdd16.get("conflicts"),
    }
    result = audit_issues(payload)
    return merge_section(state, "4", "agent4_issues", result)
