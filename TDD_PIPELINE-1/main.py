"""CLI entry point for the TDD pipeline.

Fully decoupled from fdd_pipeline: no import of it, no shared process. This
reads the FDD's structured output from a JSON file on disk -- by default
../fdd_pipeline/output/fdd_state.json, written by fdd_pipeline/main.py's own
handoff step -- and runs entirely on its own afterward.

Usage:
    python main.py                       # reads ../fdd_pipeline/output/fdd_state.json
    python main.py path/to/fdd_state.json  # reads a specific FDD run's output
"""
import json
import os
import sys
from datetime import datetime

from graph import build_graph
from pdf_export import markdown_to_pdf

DEFAULT_FDD_STATE_PATH = os.path.join("..", "fdd_pipeline", "output", "fdd_state.json")


def _new_run_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("output", f"run_{stamp}")
    suffix = 1
    while os.path.exists(run_dir):
        run_dir = os.path.join("output", f"run_{stamp}_{suffix}")
        suffix += 1
    os.makedirs(run_dir)
    return run_dir


def _load_fdd_state(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Could not find FDD state at: {path}")
        print("Run fdd_pipeline/main.py first, or pass the path to a specific")
        print("fdd_state.json as an argument to this script.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        fdd_output = json.load(f)

    if "tier" not in fdd_output or "sections" not in fdd_output:
        print(f"File at {path} doesn't look like an fdd_state.json (missing "
              "'tier' or 'sections' key).")
        sys.exit(1)

    return fdd_output


def main():
    fdd_state_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FDD_STATE_PATH
    fdd_output = _load_fdd_state(fdd_state_path)

    print(f"Loaded FDD state from: {fdd_state_path}")
    print(f"FDD tier: {fdd_output['tier']}")
    print("\nRunning the 16-agent TDD pipeline...\n")

    graph = build_graph()
    initial_state = {
        "raw_user_story": None,
        "fdd_tier": fdd_output["tier"],
        "fdd_sections": fdd_output["sections"],
        "tdd_sections": {},
        "tdd_decisions_pool": [],
    }

    final_state = graph.invoke(initial_state)
    document = final_state["final_document"]

    run_dir = _new_run_dir()

    out_path = os.path.join(run_dir, "generated_tdd.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(document)

    pdf_path = os.path.join(run_dir, "generated_tdd.pdf")
    markdown_to_pdf(out_path, pdf_path)

    handoff = {
        "fdd_tier": final_state.get("fdd_tier"),
        "tdd_included_sections": final_state.get("tdd_included_sections"),
        "tdd_sections": final_state.get("tdd_sections", {}),
    }

    # Written both into this run's own folder (history) and to a stable
    # output/tdd_state.json (so test_pipeline has one default path to read
    # without knowing the timestamp) -- same handoff pattern fdd_pipeline
    # uses for tdd_pipeline.
    state_path = os.path.join(run_dir, "tdd_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    with open(os.path.join("output", "tdd_state.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)

    print(f"Done. TDD written to {out_path}")
    print(f"PDF written to {pdf_path}")
    print(f"Stable handoff written to output/tdd_state.json (for test_pipeline)\n")
    print(document) 


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
