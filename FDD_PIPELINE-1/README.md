# FDD Multi-Agent Pipeline

A 13-agent LangGraph pipeline that generates a Functional Design Document
from a single user story. Companion implementation for
`FDD_MultiAgent_Architecture.md`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Provider settings live in the parent folder's `.env` (copy `../.env.example` to `../.env` and fill in the key). That same file is shared with the TDD, test design, and test case pipelines. Switch providers by setting `LLM_PROVIDER` to `anthropic`, `openai`, `gemini`, or `bedrock`, and setting the matching API key.

## Running

```bash
python main.py
```

Type your user story at the prompt. **Press SPACE twice in a row** to
submit it and start the workflow -- a single space just types a space,
same as normal. Press Enter for a newline if your story spans multiple
lines. Ctrl+C cancels.

On Windows the prompt uses `msvcrt`. If you pipe input instead
(`echo "..." | python main.py`, or CI), it just reads all of stdin.

Each run writes `generated_fdd.md` and `generated_fdd.pdf` under
`output/run_<YYYYMMDD_HHMMSS>/`.

Architecture (execution DAG + current data-dependency DAG):
[`FDD_MultiAgent_Architecture.md`](FDD_MultiAgent_Architecture.md).

## Structure

```
fdd_pipeline/
├── FDD_MultiAgent_Architecture.md      tiers, routing, per-agent inputs
├── main.py            CLI: story capture, per-run folder, PDF
├── graph.py           LangGraph wiring -- 5 tier nodes + classify + assemble
├── orchestrator.py    LLM classify + keyword fallback, final assembly
├── state.py           Shared StoryState TypedDict
├── llm.py             Thin wrapper: any agent -> call_agent(prompt, payload)
├── pdf_export.py      Markdown/JSON -> structured PDF
├── agents/
│   ├── common.py                       merge_section() helper
│   ├── agent1_metadata.py              Tier 1
│   ├── agent2_executive_summary.py     Tier 1 (foundational)
│   ├── agent3_conditions.py            Tier 2
│   ├── agent4_functional_requirements.py  Tier 2
│   ├── agent5_process_flow.py          Tier 3
│   ├── agent6_data_fields.py           Tier 3
│   ├── agent7_dependencies.py          Tier 3
│   ├── agent9_error_handling.py        Tier 4, optional
│   ├── agent10_localization_compliance.py  Tier 4, optional
│   ├── agent11_acceptance_criteria.py  Tier 4, required
│   ├── agent12_nfr.py                  Tier 4, optional
│   ├── agent13_transition_cutover.py   Tier 4, optional (large + cutover)
│   └── agent8_gaps_assumptions_risks.py  Tier 5, fan-in, always last
└── output/run_<timestamp>/             generated_fdd.md + .pdf
```

## Execution tiers

| Tier | Agents | Runs | Depends on |
|---|---|---|---|
| classify | LLM + keyword fallback | first | raw story text |
| 1 | Agent 1, Agent 2 | parallel | classify |
| 2 | Agent 3, Agent 4 | parallel | Agent 2 (and story) |
| 3 | Agent 5, Agent 6, Agent 7 | parallel | Agents 2/3/4 (and story for 6) |
| 4 | Agent 11 always; 9/10/12/13 if flagged | parallel | Agents 2/5/6 + `tier` for 13 |
| 5 | Agent 8 | solo, always last | all sections + assumptions_pool |
| assemble | deterministic, no LLM | last | Agent 8 + all sections |

Always-on: Agents **1–8** and **11**. Optional: **9, 10, 12, 13**.
A small story with no extra flags still runs 9 LLM agent calls
(classifier + 1–8 + 11), not 13.

## Notes on design choices

- **Graph nodes are tiers, not individual agents.** True per-agent LangGraph
  nodes with correct fan-in for a DAG this shape need either static
  multi-source edges or the `Send` API for dynamic fan-out -- both work,
  but add real complexity for a 13-node graph. Wrapping each tier's agents
  in a `ThreadPoolExecutor` inside one graph node gives the same genuine
  parallelism with far less wiring to get wrong. If you outgrow this (want
  per-agent retries, node-level observability, etc.), split each tier node
  back into individual LangGraph nodes and use `add_edge` with a list of
  source names for the joins.
- **Classify is an LLM step** (`CLASSIFIER_PROMPT`). Keyword scan is only
  the fallback. `assemble_final_document` stays deterministic (no model).
- **Every agent logs `assumptions_made`.** Agent 8 (Tier 5) reads all of
  them rather than inventing gaps and risks from scratch.
- **Keep the data DAG in sync with payloads.** LangGraph only wires tiers.
  When you add a field to an agent's `run()`, update
  `FDD_MultiAgent_Architecture.md` section 2–3.
