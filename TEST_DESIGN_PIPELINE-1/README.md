# Test Design Pipeline

A 20-agent LangGraph pipeline that generates a Test Case Design Document
from a completed FDD **and** a completed TDD (not from either document's
raw predecessor -- those were fdd_pipeline's and tdd_pipeline's jobs).
Fully decoupled from both: separate process, no shared imports. Provider
settings come from the shared `.env` one folder up. Companion implementation for
`TEST_DESIGN_MultiAgent_Architecture.md`.

## Why decoupled

fdd_pipeline, tdd_pipeline, and test_design_pipeline are three independent
programs connected only by JSON files (`fdd_state.json` -> `tdd_state.json`
-> `test_design_state.json`) written by one and read by the next. This
means:

- You can re-run test_design_pipeline against the SAME FDD/TDD output as
  many times as you want while tuning agent prompts, without burning FDD
  or TDD API calls or risking their classification changing between runs.
- A bug or prompt change in this pipeline can never accidentally affect
  the other two's imports, state shape, or environment.
- All four pipelines read the same provider settings from the `.env` one
  folder above this one.

## Setup

```bash
cd test_design_pipeline
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Provider settings live in the parent folder's `.env` (copy `../.env.example` to `../.env` and fill in the key).

## Running

First, make sure fdd_pipeline and tdd_pipeline have already produced
output:

```bash
cd ../fdd_pipeline
python main.py                 # generates output/fdd_state.json
cd ../tdd_pipeline
python main.py                 # generates output/tdd_state.json
```

Then, from test_design_pipeline:

```bash
cd ../test_design_pipeline
python main.py
    # reads ../fdd_pipeline/output/fdd_state.json
    #   and ../tdd_pipeline/output/tdd_state.json
python main.py path/to/fdd_state.json path/to/tdd_state.json
    # reads two specific runs instead -- use this whenever the two
    # default stable files don't come from matching runs
```

The pipeline warns (but does not stop) if the TDD's own recorded
`fdd_tier` doesn't match the FDD file's tier -- a hint the two files may
describe different features.

Output lands in `output/run_<timestamp>/`:
- `generated_test_design.md` -- the rendered document
- `generated_test_design.pdf` -- structured PDF of the same document
- `test_design_state.json` -- the structured output, in case a future
  test-case-writing pipeline wants to consume it, the same way
  `fdd_state.json` feeds tdd_pipeline and `tdd_state.json` feeds this one

## Structure

```
test_design_pipeline/
├── main.py             CLI: loads fdd_state.json + tdd_state.json, runs the graph, writes PDF
├── pdf_export.py       Markdown/JSON -> structured PDF
├── graph.py            LangGraph wiring -- classify + 5 tier nodes + assemble
├── orchestrator.py     Non-LLM: classify_test_design(), assemble_final_test_design()
├── state.py            TestDesignState (separate from fdd_pipeline's/tdd_pipeline's state types)
├── llm.py              Duplicated from tdd_pipeline/llm.py (see below)
├── agents/
│   ├── common.py                          merge_section() -> test_sections / assumptions_pool
│   ├── agent1_metadata.py                 Tier 1, always runs
│   ├── agent2_purpose_scope.py            Tier 1, always runs
│   ├── agent4_issues.py                   Tier 1, always runs -- broad reader, cross-document contradictions
│   ├── agent7_field_level_design.py       Tier 1, always runs
│   ├── agent3_test_basis.py               Tier 2, needs Agent 2's output
│   ├── agent5_test_strategy.py            Tier 2, needs Agent 4's output
│   ├── agent6_test_environment_data.py    Tier 2, needs Agent 2's + Agent 7's output
│   ├── agent11_positive_testing.py        Tier 3 (PT), needs Agent 4 + Agent 5
│   ├── agent12_negative_testing.py        Tier 3 (NT), needs Agent 4 + Agent 5
│   ├── agent13_boundary_testing.py        Tier 3 (BT), needs Agent 4 + Agent 5 + Agent 7
│   ├── agent14_data_validation.py         Tier 3 (DV), needs Agent 4 + Agent 5 + Agent 7
│   ├── agent15_error_handling.py          Tier 3 (EH), needs Agent 4 + Agent 5
│   ├── agent16_performance_testing.py     Tier 3 (PERF), needs Agent 4 + Agent 5
│   ├── agent17_security_testing.py        Tier 3 (SEC), needs Agent 4 + Agent 5
│   ├── agent18_usability_testing.py       Tier 3 (USAB), needs Agent 4 + Agent 5 + classify's has_ui_signal
│   ├── agent19_accessibility_testing.py   Tier 3 (ACC), needs Agent 4 + Agent 5 + classify's has_ui_signal
│   ├── agent20_compatibility_testing.py   Tier 3 (COMP), needs Agent 4 + Agent 5
│   ├── agent8_traceability_matrix.py      Tier 4, fan-in from all 10 Tier-3 agents
│   ├── agent9_entry_exit_criteria.py      Tier 4, needs Agent 4 + Agent 5 + Tier-3 priority counts
│   └── agent10_next_steps.py              Tier 5, solo, fan-in from Agent 8 + Agent 9, always last
└── output/              generated_test_design.md + .pdf + test_design_state.json, per run
```

## Agent 7 runaway generation

Agent 7 used to time out on Bedrock while the other Tier 1 agents
finished. The model was looping on long literal strings (a 50-character
max-length example typed out one character at a time), and the
non-streaming call sent nothing until that loop ended, so it looked
like a read timeout.

`llm.py` now streams every reply, aborts a repetition loop after a few
hundred characters, and retries that attempt at temperature 0.4. Agent 7
writes `<string of N chars>` instead of the literal, and a post-step
replaces any long string the model still emits. Details, env overrides
(`LLM_READ_TIMEOUT`, `LLM_MAX_OUTPUT_TOKENS`), and the token caps are in
[`AGENT7_RUNAWAY_GENERATION.md`](./AGENT7_RUNAWAY_GENERATION.md).

## Surviving a Bedrock outage

Twenty LLM calls sit behind one `python main.py`, and Tier 3 fires ten of
them at once. Bedrock answers a burst like that with
`ServiceUnavailableException` far more often than it answers the same ten
calls spread out, and the old retry schedule made it worse: the backoff
was `15s * attempt` with no jitter, so every thread in a tier woke up
together and reproduced the burst that had just failed.

Four things changed:

- **Jitter.** The wait is now a uniform draw from `[0, base * 2^(n-1)]`,
  capped at 120s, so a tier's retries spread out instead of stacking.
- **A concurrency gate.** `LLM_MAX_CONCURRENCY` (default 4) caps calls in
  flight across all threads, so Tier 3's fan-out becomes a queue. Set it
  to 1 to serialize completely while a region is struggling.
- **Adaptive botocore retries.** The Bedrock client is built with
  `Config(retries={"mode": "adaptive"}, max_pool_connections=...)`. It
  previously passed `max_retries=0`, which turned off botocore's own
  client-side rate limiting and left our loop as the only backoff. The
  pool size also mattered: the default is 10, exactly the width of Tier 3.
- **An optional fallback.** After three transient failures in a row, set
  `BEDROCK_FALLBACK_MODEL_ID` or `AWS_FALLBACK_REGION` and the call moves
  to that client for the rest of its retry budget.

If an agent still exhausts its retries, the tier no longer dies with it.
The failure is recorded in that agent's own section and the run continues,
so nineteen paid-for responses are not discarded because the twentieth hit
an outage.

## Resuming a killed run

Each tier's merged state is written to `output/.checkpoint.json` as it
completes, keyed by a hash of the two input handoff files. Re-running with
the same inputs replays the finished tiers from disk and only calls the
model for what is left:

```
Resuming: tier1 already completed for these inputs (4 sections); skipping its LLM calls.
```

The key is content-based, so editing either input invalidates it. The
checkpoint is deleted once a run assembles successfully; `python main.py
--fresh` discards it and re-runs everything.

## Why llm.py is duplicated, not shared

fdd_pipeline/llm.py, tdd_pipeline/llm.py, and test_design_pipeline/llm.py
are close but intentionally separate files. Importing one from the other
(e.g. via a shared top-level package) would break the decoupling this
design is built around -- a change to one pipeline's dependency setup
could then break another's imports at runtime. Keep all three in sync by
hand if you change LLM provider logic; the duplication cost is small and
the isolation is the point.

## Execution tiers

| Tier | Agents | Runs | Depends on |
|---|---|---|---|
| classify | -- (rule-based, no LLM) | first | FDD UI/persona signals only, for `has_ui_signal` |
| 1 | 1, 2, 4, 7 | parallel, always | fdd_sections + tdd_sections only |
| 2 | 3, 5, 6 | parallel, always | fdd_sections/tdd_sections + Tier 1's own output (2, 4, 7) |
| 3 | 11-20 (PT/NT/BT/DV/EH/PERF/SEC/USAB/ACC/COMP) | parallel, always | fdd_sections/tdd_sections + Agent 4 + Agent 5 (BT/DV also read Agent 7) |
| 4 | 8, 9 | parallel, fan-in | all ten Tier-3 scenario lists (Agent 8 in full; Agent 9 as aggregate counts) |
| 5 | 10 | solo, always last | Agent 8's coverage gaps + Agent 9's exit criteria + Agent 4's issue count |
| assemble | -- (deterministic, no LLM) | last | every `test_sections` entry, computes the coverage summary |

Unlike fdd_pipeline/tdd_pipeline, no agent here is classifier-gated --
every one of the 10 testing techniques is always evaluated, even when a
technique agent itself concludes `"applicable": false` (e.g. Accessibility
for a backend-only feature with no UI signal). The real call count is
always 20 (plus the deterministic classify/assemble steps), because
systematic technique coverage -- not skipping techniques that don't
obviously apply -- is the point of this document.

## See also

- [`TEST_DESIGN_MultiAgent_Architecture.md`](./TEST_DESIGN_MultiAgent_Architecture.md) --
  full execution DAG, data DAG, and per-agent input tables.
- [`AGENT7_RUNAWAY_GENERATION.md`](./AGENT7_RUNAWAY_GENERATION.md) --
  why Agent 7's Bedrock read timeouts were a repetition loop, and the
  streaming guard plus `<string of N chars>` descriptors that stop it.
