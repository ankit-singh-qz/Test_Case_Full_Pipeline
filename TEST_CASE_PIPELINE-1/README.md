# Test Case Pipeline

A 10-agent LangGraph pipeline that expands a completed Test Case Design
Document's scenarios (test_design_pipeline's Sections 11-20 -- PT, NT, BT,
DV, EH, PERF, SEC, USAB, ACC, COMP) into execution-ready, step-level test
cases: concrete preconditions, numbered steps with real data, and an
overall expected result -- instead of the design document's one-line
generic `expected_result` per scenario.

Fully decoupled from `fdd_pipeline`, `tdd_pipeline`, **and**
`test_design_pipeline`: separate process, no shared imports. Provider
settings come from the shared `.env` one folder up. Companion, 4th stage
after fdd_pipeline -> tdd_pipeline -> test_design_pipeline.

## Why this pipeline reads ONLY test_design_state.json

Unlike `test_design_pipeline` (which reads both `fdd_state.json` and
`tdd_state.json`, because TDD's format deliberately drops FDD's
user-facing content that some of its agents need verbatim),
`test_case_pipeline` reads **exactly one** upstream file:
`test_design_pipeline/output/test_design_state.json`. It never reads
`fdd_state.json` or `tdd_state.json`, and has no notion that either file
exists.

That one file is already self-contained for this pipeline's job:

- **Section 7** (`fields`) carries concrete `valid_examples` /
  `invalid_examples` per field plus the exact rule text -- this pipeline's
  `test_data` values are lifted straight from there.
- **Section 6** (`data_sets`, `environment_needs`) carries concrete
  numeric specifics (retry backoff windows, cache TTLs, SLA timeouts,
  token/scope test data) already pulled out of the TDD as plain text.
- **Section 4** (`issues`) carries the full contradiction text and
  `test_impact` per issue -- everything an agent needs to decide "blocked"
  vs. "expand with a stated assumption" for a given scenario.
- **Sections 11-20** (`scenarios`) often quote the original FDD/TDD line
  inline inside `src_refs` rather than just citing a section number --
  the source text itself is already there.

If a future need arises that genuinely requires re-reading the raw FDD or
TDD (not just re-deriving something test_design_pipeline already
surfaced), that is a sign test_design_pipeline itself is missing a
section, not a reason for this pipeline to reach two hops upstream.

## Setup

```bash
cd test_case_pipeline
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Provider settings live in the parent folder's `.env` (copy `../.env.example` to `../.env` and fill in the key).

## Running

First, make sure test_design_pipeline has already produced output:

```bash
cd ../fdd_pipeline && python main.py             # produces output/fdd_state.json
cd ../tdd_pipeline && python main.py             # produces output/tdd_state.json
cd ../test_design_pipeline && python main.py     # produces output/test_design_state.json
```

Then, from test_case_pipeline:

```bash
cd ../test_case_pipeline
python main.py                              # reads the default path
python main.py path/to/test_design_state.json   # reads a specific run instead
```

Output lands in `output/run_<timestamp>/`:
- `generated_test_cases.md` -- the rendered "Detailed Test Cases" document
- `generated_test_cases.pdf` -- structured PDF of the same document
- `test_case_state.json` -- the structured output, including a computed
  `coverage_summary` (ready vs. blocked, by technique, by blocking issue)

## Structure

```
test_case_pipeline/
├── main.py             CLI: loads test_design_state.json, runs the graph, writes PDF
├── pdf_export.py       Markdown/JSON -> structured PDF
├── graph.py            LangGraph wiring -- 1 tier + assemble
├── orchestrator.py     Non-LLM: compute_coverage_summary(), assemble_final_test_cases()
├── state.py            TestCaseState
├── llm.py              Duplicated from test_design_pipeline/llm.py
├── agents/
│   ├── common.py                          expand_test_cases() + merge_section()
│   ├── agent11_positive_testing.py         expands Section 11 (PT) scenarios
│   ├── agent12_negative_testing.py         expands Section 12 (NT)
│   ├── agent13_boundary_testing.py         expands Section 13 (BT)
│   ├── agent14_data_validation.py          expands Section 14 (DV)
│   ├── agent15_error_handling.py           expands Section 15 (EH)
│   ├── agent16_performance_testing.py      expands Section 16 (PERF)
│   ├── agent17_security_testing.py         expands Section 17 (SEC)
│   ├── agent18_usability_testing.py        expands Section 18 (USAB)
│   ├── agent19_accessibility_testing.py    expands Section 19 (ACC)
│   └── agent20_compatibility_testing.py    expands Section 20 (COMP)
└── output/               generated_test_cases.md + .pdf + test_case_state.json, per run
```

Each agent's own section id matches the section id it reads from
`test_design_sections` -- `agent11_positive_testing` expands
`test_design_sections["11"]` into `test_case_sections["11"]`, and so on.
This pipeline never renumbers or re-groups scenarios.

## Blocked vs. assumption -- how each agent decides

Every scenario test_design_pipeline marked with a `blocked_by_issue` is
not automatically skipped. Each technique agent looks up that issue's
`test_impact` text (from Section 4) and makes one of two calls, per
scenario, matching the `assumptions_made` convention used throughout all
four pipelines:

- **Genuinely open behavioral question** (two or more plausible correct
  answers, e.g. "cannot determine whether the SLA is 5 minutes or 5
  seconds") -> the test case is emitted as `{"status": "blocked",
  "blocked_by_issue": "I-03", "reason": "..."}` with no steps -- inventing
  an answer here would produce a test case that asserts behavior nobody
  actually decided on.
- **Narrow gap, one reasonable assumption resolves it** (e.g. no exact
  error code stated, but "rejected with a validation error" is a safe,
  literal restatement of what the source documents DO say) -> the test
  case is still expanded in full (`status: "ready"`), the assumption is
  recorded in that test case's own `reason` field AND in the section's
  `assumptions_made` array, and `blocked_by_issue` is still carried
  through for traceability even though the case is executable.

## How `expand_test_cases` works

Every technique agent calls `expand_test_cases()` in `agents/common.py`
instead of calling the model directly. A missing number, maximum, or
schema is not a pass/fail fork, but the first reply often blocks the
case anyway. This function gives that case one correction pass.

1. **First call.** The agent's system prompt plus `IO_SCHEMA` is sent
   with that agent's payload (its own `scenarios`, plus TD-4 `issues`,
   TD-6 `data_sets` / `environment_needs`, and TD-7 `fields`). The
   reply is normalized: if `blocked_by_issue` comes back as a list, it
   is joined into one string (`"I-08, I-16"`).
2. **Which blocked cases must be rewritten.** A case stays blocked only
   when its `reason` names two outcomes that would change pass/fail:
   rejected or applied, rolled back or kept, required or null. Any
   other blocked reason is flagged, including a reason that already
   says the test can proceed. An empty `scenarios` list never reaches
   this function; that agent returns without a model call.
3. **Second call, only when something was flagged.** The same prompt is
   sent again with a rewrite instruction appended, plus
   `previous_test_cases` (the full first list) and
   `rewrite_these_test_cases` (the flagged ids and their reasons). The
   model must return status `ready` with steps for those ids, keep
   `blocked_by_issue`, and state the assumption in `reason` and in
   `assumptions_made`. Real forks are left alone.
4. **Overlay.** The first reply is kept. Only the flagged ids that
   appear in the second reply are replaced. Assumptions from the second
   reply are appended. If a flagged case comes back still blocked, it
   is left as returned and the id is printed. There is no third call.

So one agent costs one model call, or two when it blocked a case for a
missing fact. Ten techniques with scenarios cost 10 calls, up to 20 if
every agent needs a rewrite. The second call stays inside that agent's
own worker; it is not a new tier.

## Execution tiers

| Tier | Agents | Runs | Depends on |
|---|---|---|---|
| 1 | 10 (agent11-agent20, one per technique) | parallel, always | `test_design_sections` only -- no agent depends on another |
| assemble | -- (deterministic, no LLM) | last | every `test_case_sections` entry; computes `coverage_summary` |

No classify step (test_design_pipeline already decided which techniques
apply and which scenarios exist -- this pipeline only expands what's
already there) and no fan-in reviewer tier (no technique agent here needs
another technique's output, unlike test_design_pipeline's traceability-
matrix/next-steps agents). Each of the 10 agents short-circuits without
an LLM call when its upstream section has zero scenarios (e.g. ACC/USAB/
COMP for a backend-only feature with no UI surface) -- it just carries
the emptiness forward with an explanatory `assumptions_made` entry
instead of wasting a call on nothing to expand.

## See also

- [`TEST_CASE_MultiAgent_Architecture.md`](./TEST_CASE_MultiAgent_Architecture.md) --
  execution tiers, the internal dependency graph (none of the 10 agents
  read each other), and the exact per-agent input slices.

## Why llm.py is duplicated, not shared

Same reasoning as the other three pipelines: importing one pipeline's
`llm.py` from another would break the decoupling this design is built
around. Keep all four in sync by hand if you change LLM provider logic;
the duplication cost is small and the isolation is the point.
