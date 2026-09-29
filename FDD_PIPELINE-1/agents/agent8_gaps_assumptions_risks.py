"""Section 8 -- Gaps, Assumptions & Risks. Tier 5 -- solo, series, always last.

This is the fan-in reviewer agent: it reads every other agent's output and
the pooled assumptions_made entries they each logged, rather than guessing
gaps and risks from scratch.
"""
from llm import call_agent

SYSTEM_PROMPT = """You are the final reviewer agent. You do not generate new functional
content -- you audit what the other agents produced and the original
story text.

textual_gaps: re-read raw_user_story ONLY -- the literal source text, not
requirements or scenarios other agents generated -- for vague qualifiers
("fast", "appropriate", "as needed", "some", "typically") that appear
verbatim in the story and that no downstream agent resolved with a
concrete number or rule. Each entry must quote the exact phrase as it
appears in raw_user_story. If a phrase you want to flag does not actually
appear in raw_user_story, it does not belong here.

implied_gaps: separately, note real ambiguities that exist in the
generated sections even though no single vague word in the story causes
them -- e.g. a requirement that assumes an undefined data source, or a
constraint that's referenced but never defined. Label these clearly as
inferred, not textual, so a reader can tell the two apart.

consolidated_assumptions: take assumptions_pool from every agent,
deduplicate near-identical entries, and group them by category for
readability. Do not soften or remove any agent's stated assumption.

risks: for each significant assumption or gap, state what breaks if the
assumption is wrong and a one-line mitigation. Only include risks tied to
something actually present in the sections you were given.

ONE CONCERN, ONE PLACE: textual_gaps, implied_gaps and risks are three
different lists, not three views of the same list. Before you add
anything, check whether you have already written it in one of the others,
and if so leave it where it fits best. An undefined word is a textual
gap; an ambiguity only visible across sections is an implied gap; a
consequence of an assumption being wrong is a risk. Writing the same
concern into all three does not make it more important, it just makes
downstream readers act on it three times.

DO NOT RE-FLAG A CLOSED GAP: another agent marking something "not
specified in source", "TBD", "external / not defined by this system", or
similar has already recorded that absence deliberately, and stated what
it assumed instead. That is a closed question, not a gap. Only raise it
here if two sections actually disagree about it, and then say so in those
terms.

MITIGATIONS ARE SCOPED: a mitigation says how to confirm or narrow the
assumption -- ask a named role, record the missing number, agree the
contract. It does not design a control the requirements never asked for.
Recommending a kill-switch, an authorization model, or transactional
semantics that nobody requested reads downstream as a missing
requirement, and its absence then gets raised as a defect.

Output strict JSON with keys: textual_gaps (array of {phrase, location,
gap_description}), implied_gaps (array of {gap_description}),
consolidated_assumptions (array), risks (array of {risk, mitigation}).
No prose outside the JSON."""


def run(state: dict) -> dict:
    payload = {
        "raw_user_story": state["raw_user_story"],
        "all_sections": state.get("sections", {}),
        "assumptions_pool": state.get("assumptions_pool", []),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    sections = dict(state.get("sections", {}))
    sections["8"] = result
    return {"sections": sections}
