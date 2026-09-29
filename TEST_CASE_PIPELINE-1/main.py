"""CLI entry point for the test_case pipeline.

Fully decoupled from fdd_pipeline, tdd_pipeline, AND test_design_pipeline:
no import of any of them, no shared process. Reads ONLY test_design_
pipeline's finished JSON handoff file from disk -- test_design_state.json
(fdd_tier + test_sections) -- and runs entirely on its own afterward.

Unlike test_design_pipeline's own main.py (which loads two upstream
files, fdd_state.json AND tdd_state.json), this pipeline loads exactly
ONE file. test_design_state.json's own sections 4/6/7/11-20 already carry
every concrete value (field examples, data sets, issue text, even inline
quotes of the original FDD/TDD lines) that expanding a scenario into
step-level test cases requires -- there is nothing left to gain by also
reading fdd_state.json or tdd_state.json directly. See README.md for the
full reasoning.

Usage:
    python main.py
        # reads ../test_design_pipeline/output/test_design_state.json
    python main.py path/to/test_design_state.json
        # reads a specific test_design_pipeline run's output instead
"""
import json
import os
import shutil
import sys
from datetime import datetime

from excel_export import load_trace_refs, write_test_cases_excel
from graph import build_graph
from orchestrator import compute_coverage_summary
from pdf_export import markdown_to_pdf

DEFAULT_TEST_DESIGN_STATE_PATH = os.path.join(
    "..", "test_design_pipeline", "output", "test_design_state.json"
)


def _new_run_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("output", f"run_{stamp}")
    suffix = 1
    while os.path.exists(run_dir):
        run_dir = os.path.join("output", f"run_{stamp}_{suffix}")
        suffix += 1
    os.makedirs(run_dir)
    return run_dir


def _load_test_design_state(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Could not find test_design state at: {path}")
        print("Run test_design_pipeline/main.py first, or pass the path to a "
              "specific test_design_state.json as an argument to this script.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if "test_sections" not in data:
        print(f"File at {path} doesn't look like a test_design_state.json "
              "(missing 'test_sections' key).")
        sys.exit(1)

    return data


def main():
    test_design_state_path = (
        sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_DESIGN_STATE_PATH
    )

    test_design_output = _load_test_design_state(test_design_state_path)

    print(f"Loaded test_design state from: {test_design_state_path}")
    print(f"FDD tier (as recorded by test_design_pipeline): "
          f"{test_design_output.get('fdd_tier', 'unknown')}")
    print("\nRunning the 10-agent test_case pipeline...\n")
    print("@@CASES_TOTAL 10", flush=True)

    graph = build_graph()
    initial_state = {
        "test_design_sections": test_design_output["test_sections"],
        "test_case_sections": {},
        "assumptions_pool": [],
    }

    final_state = graph.invoke(initial_state)
    document = final_state["final_document"]

    run_dir = _new_run_dir()

    out_path = os.path.join(run_dir, "generated_test_cases.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(document)

    pdf_path = os.path.join(run_dir, "generated_test_cases.pdf")
    markdown_to_pdf(out_path, pdf_path)

    handoff = {
        "source_test_design_path": os.path.abspath(test_design_state_path),
        "test_case_sections": final_state.get("test_case_sections", {}),
        "coverage_summary": compute_coverage_summary(final_state.get("test_case_sections", {})),
    }

    # Written both into this run's own folder (history) and to stable
    # output/test_case_state.json + output/generated_test_cases.pdf, same
    # handoff pattern the other three pipelines use.
    state_path = os.path.join(run_dir, "test_case_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    with open(os.path.join("output", "test_case_state.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    shutil.copyfile(pdf_path, os.path.join("output", "generated_test_cases.pdf"))

    xlsx_path = os.path.join(run_dir, "generated_test_cases.xlsx")
    write_test_cases_excel(
        xlsx_path,
        handoff["test_case_sections"],
        handoff["coverage_summary"],
        load_trace_refs(test_design_state_path),
    )
    shutil.copyfile(xlsx_path, os.path.join("output", "generated_test_cases.xlsx"))

    print(f"Done. Detailed test cases written to {out_path}")
    print(f"PDF written to {pdf_path}")
    print(f"Excel written to {xlsx_path}")
    print("Stable handoff written to output/test_case_state.json")
    print("Stable PDF written to output/generated_test_cases.pdf")
    print("Stable Excel written to output/generated_test_cases.xlsx\n")
    try:
        print(document)
    except UnicodeEncodeError:
        # Some Windows console code pages (e.g. cp1252) can't render every
        # character the LLM used; the files on disk are already correct
        # UTF-8, only this console echo needs a fallback.
        print(document.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
