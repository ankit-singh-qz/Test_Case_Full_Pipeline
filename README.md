# Full pipeline

One command runs FDD, TDD, test design, and test cases from a single user story. Each pipeline stays in its own folder and can still be run on its own.

## Run

From this folder, use a Python environment that has each pipeline's dependencies installed:

```bash
python run_full_pipeline.py
```

Type the user story, then press Space twice in a row to start. A single space types a space. Press Enter for a newline. Ctrl+C cancels.

Or pass a text file:

```bash
python run_full_pipeline.py path/to/story.txt
```

All four pipelines read one `.env` in this folder. Copy `.env.example` to `.env` if that file is missing, then fill in the API key. Install each folder's `requirements.txt` before the first run.

## Output

Every finished document for that story is copied into one new folder:

`output/run_<YYYYMMDD_HHMMSS>/`

- `user_story.txt`
- `run_log.txt`
- `generated_fdd.md`, `generated_fdd.pdf`, `fdd_state.json`
- `generated_tdd.md`, `generated_tdd.pdf`, `tdd_state.json`
- `generated_test_design.md`, `generated_test_design.pdf`, `test_design_state.json`
- `generated_test_cases.md`, `generated_test_cases.pdf`, `generated_test_cases.xlsx`, `test_case_state.json`

Each pipeline also keeps its own copy under that pipeline's `output/` folder. If a stage fails, the run stops and the files already produced stay in the shared folder.

## Run one pipeline alone

```bash
cd FDD_PIPELINE-1
python main.py
```

The same pattern works in `TDD_PIPELINE-1`, `TEST_DESIGN_PIPELINE-1`, and `TEST_CASE_PIPELINE-1`. Later pipelines read the previous stage's JSON; pass that path as an argument, or rely on the default path documented in that folder's README.

## Website

QA opens one page, enters `SITE_PASSWORD` from `.env`, pastes a refined user story, and presses Generate. The page then offers:

- `generated_fdd.pdf`
- `generated_tdd.pdf`
- `generated_test_design.pdf`
- `generated_test_cases.xlsx`

The site and the four pipelines run on an Oracle Cloud Always Free virtual machine, so this PC can be off. Bedrock calls are still billed to the key in `.env`. Setup steps are in [TEST_CASE_PIPELINE-1/pipeline_ui/deploy/README.md](TEST_CASE_PIPELINE-1/pipeline_ui/deploy/README.md).

To try the page on this PC first:

```bash
pip install -r TEST_CASE_PIPELINE-1/pipeline_ui/requirements.txt
cd TEST_CASE_PIPELINE-1/pipeline_ui
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Set `SITE_PASSWORD` in the root `.env` before the first login.
