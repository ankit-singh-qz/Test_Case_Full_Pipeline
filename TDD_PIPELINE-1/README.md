# TDD Pipeline

A 16-agent LangGraph pipeline that generates a Technical Design Document
from a completed FDD (not from the raw user story -- that was
fdd_pipeline's job). Fully decoupled from fdd_pipeline: separate process,
no shared imports. Provider settings come from the shared `.env` one
folder up. Companion implementation for
`TDD_MultiAgent_Architecture.md`.

## Why decoupled

fdd_pipeline and tdd_pipeline are two independent programs connected only
by a JSON file (`fdd_state.json`) written by one and read by the other.
This means:

- You can re-run tdd_pipeline against the SAME FDD output as many times as
  you want while tuning TDD agent prompts, without burning FDD API calls
  or risking the FDD's tier classification changing between runs.
- A bug or prompt change in one pipeline can never accidentally affect the
  other's imports, state shape, or environment.
- All four pipelines read the same provider settings from the `.env` one
  folder above this one.

## Setup

```bash
cd tdd_pipeline
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Provider settings live in the parent folder's `.env` (copy `../.env.example` to `../.env` and fill in the key).

## Running

First, make sure fdd_pipeline has already produced output:

```bash
cd ../fdd_pipeline
python main.py                 # generates output/fdd_state.json among other files
```

Then, from tdd_pipeline:

```bash
cd ../tdd_pipeline
python main.py                             # reads ../fdd_pipeline/output/fdd_state.json
python main.py path/to/some/fdd_state.json # reads a specific FDD run instead
```

No terminal input capture here (unlike fdd_pipeline's double-space story
entry) -- this pipeline's only input is the FDD's finished JSON, so it
just runs straight through once invoked.

Output lands in `output/run_<timestamp>/`:
- `generated_tdd.md` -- the rendered document
- `generated_tdd.pdf` -- structured PDF of the same document
- `tdd_state.json` -- the structured output, in case you want to feed this
  pipeline's output into something else later, the same way fdd_state.json
  feeds this one

## Structure

```
tdd_pipeline/
├── main.py             CLI: loads fdd_state.json, runs the graph, writes PDF
├── pdf_export.py       Markdown/JSON -> structured PDF
├── graph.py             LangGraph wiring -- 4 tier nodes + classify + assemble
├── orchestrator.py      Non-LLM: classify_tdd_sections(), assemble_final_tdd()
├── state.py             TddState (separate from fdd_pipeline's StoryState)
├── llm.py               Duplicated from fdd_pipeline/llm.py (see below)
├── agents/
│   ├── common.py                    merge_section() -> tdd_sections / tdd_decisions_pool
│   ├── agent1_metadata.py           Tier 1, always runs
│   ├── agent2_architecture.py       Tier 1, always runs
│   ├── agent4_data_model.py         Tier 1, always runs
│   ├── agent12_security.py          Tier 1, always runs
│   ├── agent3_tech_stack.py         Tier 2, optional (needs FDD NFR triggered)
│   ├── agent5_api_contracts.py      Tier 2, needs Agent 4's schema
│   ├── agent6_sequence_design.py    Tier 2, needs Agent 2's components
│   ├── agent7_background_jobs.py    Tier 2, optional
│   ├── agent8_caching.py            Tier 2, optional
│   ├── agent9_concurrency.py        Tier 2, optional
│   ├── agent10_async_events.py      Tier 2, optional, needs Agent 4's schema
│   ├── agent13_observability.py     Tier 2, optional
│   ├── agent14_deployment.py        Tier 2, optional unless large tier
│   ├── agent11_resilience.py        Tier 3, optional
│   ├── agent15_kill_switch.py       Tier 3, optional, needs Agent 4's schema
│   └── agent16_open_decisions.py    Tier 4, fan-in, always last
└── output/               generated_tdd.md + .pdf + tdd_state.json, per run
```

## Why llm.py is duplicated, not shared

fdd_pipeline/llm.py and tdd_pipeline/llm.py are byte-for-byte close but
intentionally separate files. Importing one from the other (e.g. via a
shared top-level package) would break the decoupling this design is built
around -- a change to one pipeline's dependency setup could then break the
other's imports at runtime. Keep both in sync by hand if you change LLM
provider logic; the duplication cost is small and the isolation is the
point.

## Execution tiers

| Tier | Agents | Runs | Depends on |
|---|---|---|---|
| classify | -- (rule-based, no LLM) | first | fdd_tier, fdd_sections signals only |
| 1 | 1, 2, 4, 12 | parallel, always | fdd_sections only |
| 2 | up to 9 of 3/5/6/7/8/9/10/13/14 | parallel | fdd_sections, some also read Tier 1's own output (4, 2) from this run |
| 3 | up to 2 of 11/15 | parallel | fdd_sections, 15 also reads Tier 1's Agent 4 output |
| 4 | 16 | solo, always last | every tdd_sections entry + tdd_decisions_pool |
| assemble | -- (deterministic, no LLM) | last | Agent 16's output |

For a small-tier FDD with no NFR/error-handling/external-dependency
signals, Tier 2 and Tier 3 collapse to 0 agents -- the real call count is
5 (Tier 1's four agents + Agent 16), not 16.
