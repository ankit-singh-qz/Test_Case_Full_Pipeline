"""Shared helpers every test_design agent uses to merge its output back into
state. Mirrors fdd_pipeline/agents/common.py's merge_section exactly, but
writes into test_sections and pools into assumptions_pool/assumption --
test design is a planning document dealing in stated assumptions, the same
concept fdd_pipeline uses, not the engineering decisions tdd_pipeline
tracks.

Also home to CHAR_LIMIT_RULE (appended to every agent), BLOCKING_RULE,
and normalize_scenarios. Typing out a long VARCHAR literal is what sent
Agents 7, 13, and 14 into a repetition loop; the char-limit rule tells
the model to use "<string of N chars>" instead, and compact_long_literals
is the deterministic backup on Agent 7's example arrays.

A scenario marked blocked_by_issue turns into a blocked test case
downstream, so when the technique agents disagree about when to set it
-- five of them never said anything about it at all -- the result is a
test pack where most of the work is unexecutable. BLOCKING_RULE is
appended to all ten technique prompts so they answer that question the
same way, and the normalizer repairs the shapes the models still get
wrong.
"""
import re

# Any example/input literal longer than this was written out by the model
# and is replaced by a length descriptor (see compact_long_literals).
# The prompt says 16; 32 is the safety-net threshold so ordinary short
# words are left alone.
MAX_LITERAL_CHARS = 32

# Appended to every agent that emits concrete field values or example
# strings. Typing out a VARCHAR(50) literal is what sent Agents 7, 13,
# and 14 into a repetition loop (and "A".repeat(N) then failed JSON
# parse). Descriptors keep the reply compact and countable.
CHAR_LIMIT_RULE = """

LONG STRING VALUES:
Never write out a test-input or example string longer than 16 characters.
If a value in the inputs is already a "<string of N chars>" descriptor,
copy that descriptor. For a length boundary, use "<string of N chars>"
with N from the stated limit -- e.g. VARCHAR(50): valid "<string of 50
chars>", invalid "<string of 51 chars>". Do not count characters by
typing them, and never use a code-like expression such as "A".repeat(N).
If any input/example string in your output is longer than 16 characters,
replace it with that descriptor before replying. Prose (titles, expected
results, issue text) may be longer; this rule applies only to literal
field values you would otherwise type character by character."""


def compact_long_literals(result: dict, keys=("valid_examples", "invalid_examples")) -> dict:
    """Deterministic safety net. If the model still wrote a long literal
    (which it cannot count reliably -- earlier runs used the same 40-char
    string as both the 'valid max' and 'invalid over-max' example), replace
    it with an exact descriptor computed by Python's len()."""
    if not isinstance(result, dict):
        return result
    _compact_walk(result, keys)
    return result


def _compact_walk(node, keys):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in keys and isinstance(value, list):
                node[key] = [
                    f"<string of {len(item)} chars>"
                    if isinstance(item, str) and len(item) > MAX_LITERAL_CHARS
                    else item
                    for item in value
                ]
            else:
                _compact_walk(value, keys)
    elif isinstance(node, list):
        for item in node:
            _compact_walk(item, keys)


# Appended to every technique agent's system prompt. Agents 11, 12, 14,
# 16 and 17 each had their own partial wording for this and agents 13,
# 15, 18, 19 and 20 had none, while still emitting the field -- which is
# why the captured run blocked 35 of 46 boundary scenarios, 8 of 8 error
# handling scenarios and 12 of 12 usability scenarios.
BLOCKING_RULE = """

WHEN TO SET blocked_by_issue:
blocked_by_issue is a single issue_id string from `issues` (or two joined
with ", "), or null. It is not a way to note that something is unclear --
every scenario carrying one becomes an unexecutable test case, so set it
only when all three of these hold:
1. The issue names two opposing outcomes -- rejected or applied, rolled
   back or kept, required or nullable -- not a missing fact.
2. Those two outcomes are about THIS scenario's subject. An issue about
   whether a write is persisted does not block a scenario that checks a
   message's wording, a field's length, an encryption standard, or a
   metric being emitted.
3. This scenario's own expected_result would genuinely differ depending
   on which outcome is correct.
A missing number, missing maximum, missing schema, missing SLA, or
anything the source calls "not specified" is NOT a reason to block. Write
the scenario, state the assumption you used in assumptions_made, and
leave blocked_by_issue null.
Never invent an issue_id that is not in `issues`, and never return an
array or an empty array -- use null when nothing blocks the scenario."""


def as_issue_string(value):
    """blocked_by_issue must be a string or None. Models emit bare lists,
    empty lists, and the string "null"; every downstream consumer treats
    the value as a dict key, so normalize here."""
    if value is None:
        return None
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def _as_string_list(value) -> list:
    """Coerce a src_refs/preconditions value into a list of strings.

    src_refs came back as a dict for every boundary scenario in the
    captured run, because agent 13 copies the shape of whatever it read;
    preconditions came back as one blob of prose for every data
    validation scenario. Both are declared as arrays, and the test_case
    pipeline indexes into them."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        flattened = []
        for key, item in value.items():
            for part in _as_string_list(item):
                flattened.append(f"{str(key).upper()}-{part}")
        return flattened
    if isinstance(value, list):
        flattened = []
        for item in value:
            flattened.extend(_as_string_list(item))
        return flattened
    return [str(value)]


def normalize_scenarios(result: dict, valid_issue_ids=None) -> dict:
    """Repair the scenario shapes the models keep getting wrong, and drop
    blocked_by_issue references to issues that do not exist.

    valid_issue_ids is the set of ids Agent 4 actually published. A
    reference outside it is a hallucination, and leaving it in would block
    a test case against an issue nobody can resolve."""
    scenarios = result.get("scenarios") if isinstance(result, dict) else None
    if not isinstance(scenarios, list):
        return result

    dropped = []
    normalized = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario = dict(scenario)
        scenario["src_refs"] = _as_string_list(scenario.get("src_refs"))
        scenario["preconditions"] = _as_string_list(scenario.get("preconditions"))

        blocked_by = as_issue_string(scenario.get("blocked_by_issue"))
        if blocked_by and valid_issue_ids is not None:
            referenced = [part.strip() for part in blocked_by.split(",")]
            known = [part for part in referenced if part in valid_issue_ids]
            if len(known) != len(referenced):
                dropped.extend(part for part in referenced if part not in valid_issue_ids)
            blocked_by = ", ".join(known) if known else None
        scenario["blocked_by_issue"] = blocked_by
        normalized.append(scenario)

    if dropped:
        print(
            "Cleared blocked_by_issue references to unknown issues: "
            + ", ".join(sorted(set(dropped))),
            flush=True,
        )

    out = dict(result)
    out["scenarios"] = normalized
    return out


def issue_ids(state: dict) -> set:
    """The issue ids Agent 4 published for this run."""
    section4 = (state.get("test_sections") or {}).get("4") or {}
    return {
        issue.get("issue_id")
        for issue in (section4.get("issues") or [])
        if isinstance(issue, dict) and issue.get("issue_id")
    }


def merge_section(state: dict, section_id: str, agent_name: str, result: dict) -> dict:
    sections = dict(state.get("test_sections", {}))
    sections[section_id] = result

    pool = list(state.get("assumptions_pool", []))
    for assumption in result.get("assumptions_made", []) or []:
        pool.append({"source_agent": agent_name, "assumption": assumption})

    return {"test_sections": sections, "assumptions_pool": pool}


def substitute_placeholders(result: dict, replacements: dict, keys) -> dict:
    """Replace literal placeholder tokens (e.g. "{P1_COUNT}") with their
    real values, across every string in the named list-of-strings fields
    of result.

    Some sections need a Python-computed number (a scenario count, an
    open-issue count) to appear inside an LLM-written sentence. Simply
    telling the model "use this number verbatim, don't recompute it"
    is not reliable even with an explicit rule and a SELF-CHECK -- a
    fast/cheap model can still retype the number wrong (observed:
    off-by-one on a scenario count, and a stale count on an issues
    total). Instead, the prompt tells the model to write the placeholder
    token literally, and this function substitutes the real value
    afterward -- deterministically, with no chance of a typo."""
    updated = dict(result)
    for key in keys:
        values = updated.get(key)
        if not isinstance(values, list):
            continue
        new_values = []
        for v in values:
            if isinstance(v, str):
                for token, real_value in replacements.items():
                    v = v.replace(token, str(real_value))
            new_values.append(v)
        updated[key] = new_values
    return updated


def fix_open_issue_count(result: dict, real_count: int, keys) -> dict:
    """Belt-and-suspenders correction for one specific, observed model
    bias: even when told to write the {OPEN_ISSUE_COUNT} placeholder
    instead of typing a digit, the model has been seen to write a
    literal, stale-looking digit right before the phrase "open issues"
    anyway (e.g. always "20", regardless of the real count, which was
    26 in one run and 25 in the next) -- while correctly using the
    placeholder elsewhere in that SAME call. substitute_placeholders()
    only fixes the token when the model actually wrote it; this second,
    regex-based pass catches the case where it didn't and just typed a
    number instead, so a wrong count can't slip through silently."""
    pattern = re.compile(r"\b\d+(?=\s+open issue)", re.IGNORECASE)
    updated = dict(result)
    for key in keys:
        values = updated.get(key)
        if not isinstance(values, list):
            continue
        updated[key] = [
            pattern.sub(str(real_count), v) if isinstance(v, str) else v for v in values
        ]
    return updated
