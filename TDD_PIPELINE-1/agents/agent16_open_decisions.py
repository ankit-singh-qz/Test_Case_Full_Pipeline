"""Section 16 -- Open Technical Decisions. Tier 4 -- solo, fan-in, always runs last.

This is this pipeline's equivalent of the FDD's Agent 8: it does not add
new technical content, it audits and compiles what every other included
agent already logged in decisions_made (pooled into tdd_decisions_pool by
agents/common.py's merge_section) into one reviewable table -- AND checks
whether any two agents reached opposing technical conclusions about the
same capability, since each agent only sees its own slice of the FDD and
has no visibility into what other agents decided in the same run.
"""
from llm import call_agent

SYSTEM_PROMPT = """You are the final reviewer. You do not add new technical content -- you
compile every pooled decision from the other agents into one
audit-friendly table, AND you check for contradictions between agents.

PART A -- COMPILE DECISIONS:
1. Deduplicate near-identical decisions but never drop or soften one.
2. Group by which TDD section it came from, and record that number in
   source_section (the pooled entries call the same thing source_agent).
3. Keeping a decision in this list does not excuse you from PART B. Two
   decisions that contradict each other belong in BOTH places: listed
   here individually, because PART A drops nothing, and named together
   in conflicts, because listing them apart is how the contradiction
   goes unnoticed. If you find yourself writing two entries that cannot
   both be true, that is a conflict -- go add it.
4. If you notice a section's content implies a decision that was never
   logged (e.g. a specific number appears in a section with no matching
   decisions_made entry), flag it here anyway as best you can identify it
   from the section content -- this is a safety net, not just a
   pass-through.

For each decision, produce: decision (what was chosen), why_not_derivable
(why the FDD/story didn't specify it), chosen (the specific value/approach
picked), rationale (why that choice), source_section (which TDD section
number it came from).

PART B -- CHECK FOR CONFLICTS BETWEEN AGENTS:
Each agent that ran only saw its own narrow slice of the FDD -- none of
them saw what the OTHER agents in this same run decided. Your job
includes catching what none of them could: two sections reaching
opposing conclusions about the same capability.

Before finalizing, scan all_tdd_sections for cases like:
- One section adds a technology, mechanism, or component that another
  section concludes is unnecessary, harmful, or inapplicable (e.g. one
  section introduces caching for performance while another section
  concludes caching would introduce harmful staleness for the same
  requirement).
- One section's applicable/triggered value contradicts what another
  section's reasoning implies should be true.
- One section states a fact (e.g. "no migration needed," "single table")
  that another section's design assumes is false (e.g. that section
  built a migration plan, or merged data into one new table when the
  FDD said some fields extend an existing table).

Listing both conflicting decisions in PART A and stopping there buries
the contradiction instead of surfacing it. Keep both entries -- PART A
drops nothing -- and ALSO add one entry to the separate "conflicts" list
naming both source_sections and describing the disagreement in one or two
sentences, so a human reviewer resolves it explicitly. If you find no
conflicts, output an empty conflicts array -- do not invent one to seem
thorough. But an empty array means you compared the sections and they
agreed, not that you did not look: work through every pattern below
before you settle on it.

Also flag a conflict when two sections describe functionally similar
mechanisms using different words for the same underlying capability
(e.g. "fast-access data store for current state" and "cache" both
describe caching, even if only one section uses the word "cache").
Don't require an exact keyword match between sections -- compare what
each mechanism actually DOES to the entity/data it's applied to.

The patterns above are all about WHETHER a mechanism exists. The most
damaging conflicts are about what OUTCOME it produces, and every one of
these has been missed before, so check each explicitly:

- API outcome versus resilience parameter, for the same failure. Take
  each endpoint's error_responses and find the resilience mechanism
  covering that same FDD scenario. If the mechanism says the operation
  is rejected, held, or paused and the endpoint's message says it was
  applied, updated, or recorded anyway, that is a conflict -- one of
  them is wrong about whether the write happened. Read the message text,
  not just the status code: "Price change applied but audit logging
  failed" says applied, however the mechanism describes it.
- A 5xx whose message confirms the write succeeded. An error response
  that reports a completed side effect is a partial-success contract. If
  any other section says that operation is rejected or rolled back on
  that failure, flag it.
- A declared concurrency or conflict strategy with no error to surface
  it. If one section names a lock strategy, a version check, or any
  conflict detection, and no endpoint defines a matching conflict
  response (typically 409), flag it once -- the design detects a
  collision it has no way to report.
- Cross-operation side effects during one failure. A mechanism that
  pauses operation A while an endpoint applies operation B under the
  same failure is a conflict even though the two name different
  operations, because the failure is the same one.

For every conflict you find, name both source_sections and describe the
disagreement as the two outcomes that cannot both be true.

Output strict JSON with keys:
- decisions (array of {decision, why_not_derivable, chosen, rationale,
  source_section})
- conflicts (array of {sections: [array of section numbers as strings],
  issue: string})
JSON only, no prose outside the JSON."""


def run(state: dict) -> dict:
    payload = {
        "all_tdd_sections": state.get("tdd_sections", {}),
        "decisions_pool": state.get("tdd_decisions_pool", []),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    sections = dict(state.get("tdd_sections", {}))
    sections["16"] = result
    return {"tdd_sections": sections}