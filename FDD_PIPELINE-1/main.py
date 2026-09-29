"""CLI entry point for the FDD pipeline.

Type the user story, then press SPACE twice in a row to submit it and kick
off the 13-agent workflow. Enter/newline lets you write a multi-line story;
only a double space triggers the run -- a single space just types a space.

Character-by-character capture uses termios/tty on POSIX and msvcrt on
Windows. If stdin isn't an interactive terminal (piped input, CI,
redirected from a file), it falls back to reading everything from stdin
in one shot instead.
"""
import json
import os
import sys
from datetime import datetime

from graph import build_graph
from pdf_export import markdown_to_pdf


def _new_run_dir() -> str:
    """Create a unique output/run_<timestamp>/ folder for this invocation."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join("output", f"run_{stamp}")
    suffix = 1
    while os.path.exists(run_dir):
        run_dir = os.path.join("output", f"run_{stamp}_{suffix}")
        suffix += 1
    os.makedirs(run_dir)
    return run_dir



def _prompt_story() -> None:
    print("Enter your user story below.")
    print("Press SPACE twice in a row to submit and start the workflow.\n")
    print("> ", end="", flush=True)


def _consume_char(buffer: list[str], ch: str, last_was_space: bool) -> tuple[bool, bool]:
    """Handle one typed character. Returns (done, last_was_space)."""
    if ch == "\x03":  # Ctrl+C
        raise KeyboardInterrupt

    if ch in ("\r", "\n"):
        buffer.append("\n")
        sys.stdout.write("\n")
        return False, False

    if ch in ("\x08", "\x7f"):  # Backspace
        if buffer:
            buffer.pop()
            sys.stdout.write("\b \b")
        return False, False

    if ch == " ":
        if last_was_space:
            # Second consecutive space -> submit. Drop the first
            # space we already buffered/echoed so it doesn't leak
            # into the story text.
            if buffer and buffer[-1] == " ":
                buffer.pop()
            sys.stdout.write("\n")
            return True, False
        buffer.append(ch)
        sys.stdout.write(ch)
        return False, True

    buffer.append(ch)
    sys.stdout.write(ch)
    return False, False


def _read_story_interactive_posix() -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer: list[str] = []
    last_was_space = False
    _prompt_story()

    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            done, last_was_space = _consume_char(buffer, ch, last_was_space)
            sys.stdout.flush()
            if done:
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return "".join(buffer).strip()


def _read_story_interactive_windows() -> str:
    import msvcrt

    buffer: list[str] = []
    last_was_space = False
    _prompt_story()

    while True:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()  # skip arrow / function-key scan code
            continue
        done, last_was_space = _consume_char(buffer, ch, last_was_space)
        sys.stdout.flush()
        if done:
            break

    return "".join(buffer).strip()


def _read_story_interactive() -> str:
    if sys.platform == "win32":
        return _read_story_interactive_windows()
    return _read_story_interactive_posix()


def _read_story() -> str:
    if sys.stdin.isatty():
        return _read_story_interactive()
    # Non-interactive fallback: piped input, CI, redirected file, etc.
    print("Non-interactive stdin detected -- reading full input instead of "
          "waiting for a double space.")
    return sys.stdin.read().strip()


def main():
    story = _read_story()
    if not story:
        print("No story entered. Exiting.")
        return

    print("\nWorkflow started -- running the 13-agent pipeline...\n")

    graph = build_graph()
    initial_state = {
        "raw_user_story": story,
        "ticket_metadata": None,
        "sections": {},
        "assumptions_pool": [],
    }

    final_state = graph.invoke(initial_state)
    document = final_state["final_document"]

    run_dir = _new_run_dir()
    out_path = os.path.join(run_dir, "generated_fdd.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(document)

    pdf_path = os.path.join(run_dir, "generated_fdd.pdf")
    markdown_to_pdf(out_path, pdf_path)

    # Handoff artifact for the (decoupled) tdd_pipeline: the FDD's structured
    # state, not just its rendered Markdown. Written both into this run's
    # folder (history) and to a stable output/fdd_state.json (so the TDD
    # pipeline has one default path to read without knowing the timestamp).
    handoff = {"tier": final_state.get("tier"), "sections": final_state.get("sections", {})}
    with open(os.path.join(run_dir, "fdd_state.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
    with open(os.path.join("output", "fdd_state.json"), "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)

    print(f"Done. FDD written to {out_path}")
    print(f"PDF written to {pdf_path}")
    print(f"Structured handoff written to output/fdd_state.json (for tdd_pipeline)\n")
    print(document)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
