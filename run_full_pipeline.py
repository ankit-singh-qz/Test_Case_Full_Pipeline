"""Run FDD, TDD, test design, and test cases from one user story.

Each pipeline stays in its own folder and is started as its own process.
All four read the shared .env in this folder. Finished documents are copied
into one new output/run_<timestamp>/ folder.

    python run_full_pipeline.py
    python run_full_pipeline.py path/to/story.txt
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STAGES = (
    {
        "name": "FDD",
        "folder": "FDD_PIPELINE-1",
        "use_stdin": True,
        "artifacts": ["generated_fdd.md", "generated_fdd.pdf", "fdd_state.json"],
        "required": "fdd_state.json",
        "pass_files": [],
    },
    {
        "name": "TDD",
        "folder": "TDD_PIPELINE-1",
        "use_stdin": False,
        "artifacts": ["generated_tdd.md", "generated_tdd.pdf", "tdd_state.json"],
        "required": "tdd_state.json",
        "pass_files": ["fdd_state.json"],
    },
    {
        "name": "test design",
        "folder": "TEST_DESIGN_PIPELINE-1",
        "use_stdin": False,
        "artifacts": [
            "generated_test_design.md",
            "generated_test_design.pdf",
            "test_design_state.json",
        ],
        "required": "test_design_state.json",
        "pass_files": ["fdd_state.json", "tdd_state.json"],
    },
    {
        "name": "test cases",
        "folder": "TEST_CASE_PIPELINE-1",
        "use_stdin": False,
        "artifacts": [
            "generated_test_cases.md",
            "generated_test_cases.pdf",
            "generated_test_cases.xlsx",
            "test_case_state.json",
        ],
        "required": "test_case_state.json",
        "pass_files": ["test_design_state.json"],
    },
)

_current_proc: subprocess.Popen | None = None


def _new_run_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "output" / f"run_{stamp}"
    suffix = 1
    while run_dir.exists():
        run_dir = ROOT / "output" / f"run_{stamp}_{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _prompt_story() -> None:
    print("Enter your user story below.")
    print("Press SPACE twice in a row to submit and start the workflow.\n")
    print("> ", end="", flush=True)


def _consume_char(buffer: list[str], ch: str, last_was_space: bool) -> tuple[bool, bool]:
    """Handle one typed character. Returns (done, last_was_space)."""
    if ch == "\x03":
        raise KeyboardInterrupt

    if ch in ("\r", "\n"):
        buffer.append("\n")
        sys.stdout.write("\n")
        return False, False

    if ch in ("\x08", "\x7f"):
        if buffer:
            buffer.pop()
            sys.stdout.write("\b \b")
        return False, False

    if ch == " ":
        if last_was_space:
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
            msvcrt.getwch()
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
    if len(sys.argv) > 2:
        print("Usage: python run_full_pipeline.py [path/to/story.txt]")
        sys.exit(1)

    if len(sys.argv) == 2:
        path = Path(sys.argv[1])
        if not path.is_file():
            print(f"Could not find story file: {path}")
            sys.exit(1)
        return path.read_text(encoding="utf-8-sig").strip()

    if sys.stdin.isatty():
        return _read_story_interactive()

    print("Non-interactive stdin detected -- reading full input instead of "
          "waiting for a double space.")
    return sys.stdin.read().strip()


def _snapshot_runs(pipeline_dir: Path) -> set[str]:
    output = pipeline_dir / "output"
    if not output.is_dir():
        return set()
    return {
        path.name
        for path in output.iterdir()
        if path.is_dir() and path.name.startswith("run_")
    }


def _new_pipeline_run(pipeline_dir: Path, before: set[str]) -> Path | None:
    output = pipeline_dir / "output"
    if not output.is_dir():
        return None
    created = [
        path
        for path in output.iterdir()
        if path.is_dir() and path.name.startswith("run_") and path.name not in before
    ]
    if not created:
        return None
    return max(created, key=lambda path: path.stat().st_mtime)


def _copy_artifacts(run_dir: Path, source: Path, names: list[str]) -> list[str]:
    copied = []
    for name in names:
        src = source / name
        if src.is_file():
            shutil.copy2(src, run_dir / name)
            copied.append(name)
    return copied


def _run_stage(stage: dict, run_dir: Path, story: str, log_path: Path) -> int:
    global _current_proc

    pipeline_dir = ROOT / stage["folder"]
    main_py = pipeline_dir / "main.py"
    if not main_py.is_file():
        print(f"Could not find {main_py}")
        return 1

    command = [sys.executable, "-u", "main.py"]
    for name in stage["pass_files"]:
        command.append(str((run_dir / name).resolve()))

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n--- {stage['name']} ---\n")
    before = _snapshot_runs(pipeline_dir)

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== {stage['name']} =====\n")
        log.flush()
        proc = subprocess.Popen(
            command,
            cwd=pipeline_dir,
            stdin=subprocess.PIPE if stage["use_stdin"] else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        _current_proc = proc
        if stage["use_stdin"] and proc.stdin is not None:
            proc.stdin.write(story.encode("utf-8"))
            proc.stdin.close()

        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
        return_code = proc.wait()
        _current_proc = None
        log.write(f"\n===== {stage['name']} exit {return_code} =====\n")
        log.flush()

    produced = _new_pipeline_run(pipeline_dir, before)
    copied: list[str] = []
    if produced is not None:
        copied = _copy_artifacts(run_dir, produced, stage["artifacts"])

    required = run_dir / stage["required"]
    if return_code != 0 or not required.is_file():
        detail = f"The {stage['name']} pipeline exited with status {return_code}."
        if not required.is_file():
            detail += f" {stage['required']} was not written."
        if produced is None:
            detail += " No new run folder was created in that pipeline."
        print(f"\nStopped after {stage['name']}. {detail}")
        print(f"Files written so far are in:\n  {run_dir}")
        print(f"Console output is in:\n  {log_path}")
        return return_code or 1

    missing = [name for name in stage["artifacts"] if name not in copied]
    if missing:
        print(f"Warning: {stage['name']} did not produce: {', '.join(missing)}")
    print(f"\n{stage['name']} written to {run_dir}")
    return 0


def _summarize(run_dir: Path) -> None:
    print(f"\nDone. All four documents are in:\n  {run_dir}\n")
    for stage in STAGES:
        for name in stage["artifacts"]:
            path = run_dir / name
            if path.is_file():
                print(f"  {name}")


def main() -> None:
    story = _read_story()
    if not story:
        print("No story entered. Exiting.")
        return

    run_dir = _new_run_dir()
    (run_dir / "user_story.txt").write_text(story, encoding="utf-8")
    log_path = run_dir / "run_log.txt"
    log_path.write_text(
        f"Run folder: {run_dir}\nStarted: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding="utf-8",
    )

    print(f"\nWorkflow started. Output folder:\n  {run_dir}\n")

    for stage in STAGES:
        code = _run_stage(stage, run_dir, story, log_path)
        if code != 0:
            sys.exit(code)

    _summarize(run_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        if _current_proc is not None and _current_proc.poll() is None:
            _current_proc.terminate()
        print("\nCancelled.")
        sys.exit(1)
