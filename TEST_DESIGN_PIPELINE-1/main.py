"""CLI entry point for the test_design pipeline.

Fully decoupled from fdd_pipeline/tdd_pipeline: no import of either, no
shared process. Reads BOTH finished JSON handoff files from disk --
fdd_state.json (tier + sections) and tdd_state.json (fdd_tier +
tdd_included_sections + tdd_sections) -- and runs entirely on its own
afterward.

Usage:
    python main.py
        # reads ../fdd_pipeline/output/fdd_state.json
        #   and ../tdd_pipeline/output/tdd_state.json
    python main.py path/to/fdd_state.json path/to/tdd_state.json
        # reads two specific runs -- use this whenever the two default
        # stable files don't come from the same run pairing
    python main.py --fresh
        # ignore output/.checkpoint.json and re-run every tier
"""
import json
import os
import shutil
import sys
from datetime import datetime

import checkpoint
from graph import build_graph
from pdf_export import markdown_to_pdf

DEFAULT_FDD_STATE_PATH = os.path.join("..", "fdd_pipeline", "output", "fdd_state.json")
DEFAULT_TDD_STATE_PATH = os.path.join("..", "tdd_pipeline", "output", "tdd_state.json")


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
        print("fdd_state.json as the first argument to this script.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        fdd_output = json.load(f)

    if "tier" not in fdd_output or "sections" not in fdd_output:
        print(f"File at {path} doesn't look like an fdd_state.json (missing "
              "'tier' or 'sections' key).")
        sys.exit(1)

    return fdd_output


def _load_tdd_state(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Could not find TDD state at: {path}")
        print("Run tdd_pipeline/main.py first, or pass the path to a specific")
        print("tdd_state.json as the second argument to this script.")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        tdd_output = json.load(f)

    if "tdd_sections" not in tdd_output or "tdd_included_sections" not in tdd_output:
        print(f"File at {path} doesn't look like a tdd_state.json (missing "
              "'tdd_sections' or 'tdd_included_sections' key).")
        sys.exit(1)

    return tdd_output


def main():
    args = [arg for arg in sys.argv[1:] if arg != "--fresh"]
    fresh = "--fresh" in sys.argv[1:]
    fdd_state_path = args[0] if len(args) > 0 else DEFAULT_FDD_STATE_PATH
    tdd_state_path = args[1] if len(args) > 1 else DEFAULT_TDD_STATE_PATH

    if fresh:
        checkpoint.clear()
        print("--fresh: discarded any existing checkpoint.")

    fdd_output = _load_fdd_state(fdd_state_path)
    tdd_output = _load_tdd_state(tdd_state_path)

    if tdd_output.get("fdd_tier") and tdd_output["fdd_tier"] != fdd_output["tier"]:
        print(
            f"WARNING: FDD tier ({fdd_output['tier']}) and the TDD's recorded "
            f"fdd_tier ({tdd_output['fdd_tier']}) don't match -- these two "
            "files may be from different runs and not describe the same feature."
        )

    print(f"Loaded FDD state from: {fdd_state_path}")
    print(f"Loaded TDD state from: {tdd_state_path}")
    print(f"FDD tier: {fdd_output['tier']}")
    print(f"TDD included sections: {tdd_output['tdd_included_sections']}")
    print("\nRunning the 20-agent test design pipeline...\n")
    print("@@DESIGN_TOTAL 20", flush=True)

    graph = build_graph()
    initial_state = {
        "fdd_tier": fdd_output["tier"],
        "fdd_sections": fdd_output["sections"],
        "tdd_included_sections": tdd_output["tdd_included_sections"],
        "tdd_sections": tdd_output["tdd_sections"],
        "checkpoint_key": checkpoint.input_key(fdd_state_path, tdd_state_path),
        "test_sections": {},
        "assumptions_pool": [],
    }

    final_state = graph.invoke(initial_state)
    document = final_state["final_document"]

    # The document assembled, so nothing is left to resume.
    checkpoint.clear()

    run_dir = _new_run_dir()

    out_path = os.path.join(run_dir, "generated_test_design.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(document)

    pdf_path = os.path.join(run_dir, "generated_test_design.pdf")
    markdown_to_pdf(out_path, pdf_path)

    handoff = {
        "fdd_tier": final_state.get("fdd_tier"),
        "source_fdd_path": os.path.abspath(fdd_state_path),
        "source_tdd_path": os.path.abspath(tdd_state_path),
        "test_sections": final_state.get("test_sections", {}),
    }

    # Written both into this run's own folder (history) and to stable
    # output/test_design_state.json + output/generated_test_design.pdf,
    # same handoff pattern fdd_pipeline uses for tdd_pipeline and
    # tdd_pipeline uses for this pipeline -- the stable PDF sits next to
    # the stable JSON so either one alone is enough to hand off.
    state_path = os.path.join(run_dir, "test_design_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    with open(os.path.join("output", "test_design_state.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    shutil.copyfile(pdf_path, os.path.join("output", "generated_test_design.pdf"))

    print(f"Done. Test design written to {out_path}")
    print(f"PDF written to {pdf_path}")
    print("Stable handoff written to output/test_design_state.json")
    print("Stable PDF written to output/generated_test_design.pdf\n")
    try:
        print(document)
    except UnicodeEncodeError:
        # Some Windows console code pages (e.g. cp1252) can't render every
        # character the LLM used (e.g. an arrow "->" typed as U+2192). The
        # files on disk are already correct UTF-8; only this console echo
        # needs a fallback.
        print(document.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
