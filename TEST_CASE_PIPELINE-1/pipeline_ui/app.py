"""Website that runs the four document pipelines from one user story.

This process does not import those pipelines. It starts run_full_pipeline.py
in the workspace root, which loads the shared .env and writes one output folder.
"""
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

UI_DIR = Path(__file__).resolve().parent
STATIC_DIR = UI_DIR / "static"

RUN_ID_RE = re.compile(r"^run_\d{8}_\d{6}(?:_\d+)?$")
STAGE_LINE = re.compile(r"^---\s+(.+?)\s+---\s*$")
PROGRESS_LINE = re.compile(r"^@@(FDD|TDD|DESIGN|CASES)_(STEP|TOTAL)(?:\s+(\d+))?\s*$")
PROGRESS_DONE = {"FDD": "fdd_done", "TDD": "tdd_done", "DESIGN": "design_done", "CASES": "cases_done"}
PROGRESS_TOTAL = {"FDD": "fdd_total", "TDD": "tdd_total", "DESIGN": "design_total", "CASES": "cases_total"}
STOPPED_LINE = re.compile(r"^Stopped after .+", re.IGNORECASE)
STATUS_LINE = re.compile(
    r"^(---|Workflow started|Non-interactive|LLM request|Rewriting |"
    r"Still blocked|Resuming:|Tier finished|Loaded |FDD tier|TDD included|"
    r"Running the|Done\.|PDF written|Excel written|Stable |Structured handoff|"
    r"WARNING:|Could not|File at |Stopped after|Cancelled|"
    r"written to )",
    re.IGNORECASE,
)
STAGES = ("FDD", "TDD", "test design", "test cases")
FILES = (
    "generated_fdd.pdf",
    "generated_tdd.pdf",
    "generated_test_design.pdf",
    "generated_test_cases.xlsx",
)
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
LOG_LINE_LIMIT = 80
STORY_MAX_CHARS = 200_000
COOKIE = "site_auth"

_lock = threading.Lock()
_job = {"run_id": None, "proc": None, "busy": False}


def _find_root() -> Path:
    for candidate in (UI_DIR.parents[1], UI_DIR.parent):
        if (candidate / "run_full_pipeline.py").is_file():
            return candidate
    raise RuntimeError("Could not find run_full_pipeline.py above the website.")


ROOT = _find_root()
OUTPUT_DIR = ROOT / "output"
load_dotenv(ROOT / ".env")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _site_password() -> str:
    return os.getenv("SITE_PASSWORD", "").strip()


def _auth_token() -> str:
    password = _site_password()
    if not password:
        return ""
    return hmac.new(password.encode("utf-8"), b"site-auth", hashlib.sha256).hexdigest()


def _authorized(site_auth: str | None) -> bool:
    expected = _auth_token()
    if not expected or not site_auth:
        return False
    return hmac.compare_digest(site_auth, expected)


def _require(site_auth: str | None) -> None:
    if not _site_password():
        raise HTTPException(status_code=503, detail="Set SITE_PASSWORD in the server .env.")
    if not _authorized(site_auth):
        raise HTTPException(status_code=401, detail="Enter the site password.")


def _run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id or ""):
        raise HTTPException(status_code=404, detail="Run not found.")
    path = OUTPUT_DIR / run_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Run not found.")
    return path


def _preview(story: str) -> str:
    line = " ".join(story.split())
    return line[:80]


def _read_story(run_dir: Path) -> str:
    try:
        return (run_dir / "user_story.txt").read_text(encoding="utf-8")
    except OSError:
        return ""


def _present_files(run_dir: Path) -> list[str]:
    return [name for name in FILES if (run_dir / name).is_file()]


def _failure_detail(run_dir: Path) -> str:
    """The pipeline's own last error, from this run's log only."""
    path = run_dir / "run_log.txt"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines[-120:]):
        text = line.strip()
        if not text or text.startswith("====="):
            continue
        if text.startswith('"') or text.startswith("{") or text.startswith("}"):
            continue
        if "Exception:" in text or text.startswith("Error:"):
            return text[:500]
    return ""


def _read_status(run_dir: Path) -> dict:
    path = run_dir / "ui_status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    files = _present_files(run_dir)
    status = data.get("status") or ("succeeded" if len(files) == len(FILES) else "partial")
    error = data.get("error") or ""
    log = data.get("log") or ""
    detail = _failure_detail(run_dir) if status == "failed" else ""
    if detail and detail not in error:
        error = f"{error}\n{detail}".strip() if error else detail
    if detail and detail not in log:
        log = f"{log}\n{detail}".strip() if log else detail
    return {
        "id": run_dir.name,
        "created_at": data.get("created_at"),
        "story_preview": data.get("story_preview") or _preview(_read_story(run_dir)),
        "status": status,
        "stage": data.get("stage") or "",
        **_progress_values(data),
        "error": error,
        "log": log,
        "files": files,
    }


def _progress_values(data: dict | None) -> dict:
    source = data or {}
    values = {}
    for name in (*PROGRESS_DONE.values(), *PROGRESS_TOTAL.values()):
        values[name] = int(source.get(name) or 0)
    return values


def _write_status(run_dir: Path, payload: dict) -> None:
    path = run_dir / "ui_status.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _list_run_dirs() -> list[Path]:
    if not OUTPUT_DIR.is_dir():
        return []
    found = []
    for path in OUTPUT_DIR.iterdir():
        if path.is_dir() and RUN_ID_RE.fullmatch(path.name) and (path / "user_story.txt").is_file():
            found.append(path)
    found.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return found


def recover_interrupted() -> None:
    for run_dir in _list_run_dirs():
        status = _read_status(run_dir)
        if status["status"] != "running":
            continue
        status["status"] = "failed"
        status["error"] = "The server restarted while this run was in progress. Generate again to retry."
        status["finished_at"] = _now()
        _write_status(run_dir, status)


def _append_status(bucket: list[str], line: str) -> None:
    text = line.strip()
    if not text or not STATUS_LINE.match(text):
        return
    bucket.append(text[:500])
    del bucket[:-LOG_LINE_LIMIT]


def _note_folder(line: str, state: dict) -> None:
    candidate = line.strip().strip('"')
    if not candidate:
        return
    path = Path(candidate)
    try:
        resolved = path.resolve()
    except (OSError, ValueError):
        return
    if resolved.parent != OUTPUT_DIR.resolve() or not RUN_ID_RE.fullmatch(resolved.name):
        return
    state["run_dir"] = resolved
    state["run_id"] = resolved.name


def _run_pipeline(story: str) -> None:
    status_lines: list[str] = []
    tail: list[str] = []
    state = {
        "run_dir": None,
        "run_id": None,
        "stage": "Starting",
        "status": "running",
        **_progress_values({}),
        "error": "",
        "created_at": _now(),
        "story_preview": _preview(story),
    }
    last_flush = 0.0
    story_path = ""

    def snapshot() -> dict:
        run_dir = state["run_dir"]
        files = _present_files(run_dir) if run_dir and run_dir.is_dir() else []
        return {
            "id": state["run_id"],
            "created_at": state["created_at"],
            "story_preview": state["story_preview"],
            "status": state["status"],
            "stage": state["stage"],
            **_progress_values(state),
            "error": state["error"],
            "log": "\n".join(status_lines),
            "files": files,
            "finished_at": state.get("finished_at"),
        }

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        now = datetime.now(timezone.utc).timestamp()
        if not force and now - last_flush < 1:
            return
        last_flush = now
        run_dir = state["run_dir"]
        if run_dir and run_dir.is_dir():
            _write_status(run_dir, snapshot())

    try:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", prefix="story_", encoding="utf-8", delete=False
        )
        handle.write(story)
        handle.close()
        story_path = handle.name

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "run_full_pipeline.py"), story_path],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        with _lock:
            _job["proc"] = proc

        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            text = line.rstrip()
            tail.append(text[:500])
            del tail[-40:]
            stripped = text.strip()
            stage_match = STAGE_LINE.match(stripped)
            if stage_match and stage_match.group(1) in STAGES:
                state["stage"] = stage_match.group(1)
            progress = PROGRESS_LINE.match(stripped)
            if progress:
                kind, what, count = progress.group(1), progress.group(2), progress.group(3)
                if what == "STEP":
                    key = PROGRESS_DONE[kind]
                    state[key] = int(state.get(key) or 0) + 1
                elif count:
                    state[PROGRESS_TOTAL[kind]] = int(count)
            _note_folder(text, state)
            if state["run_id"]:
                with _lock:
                    _job["run_id"] = state["run_id"]
            stopped = STOPPED_LINE.match(text.strip())
            if stopped:
                state["error"] = text.strip()
            _append_status(status_lines, text)
            flush()
        return_code = proc.wait()
        flush(force=True)
        files = _present_files(state["run_dir"]) if state["run_dir"] else []
        if return_code == 0 and len(files) == len(FILES):
            state["status"] = "succeeded"
            state["stage"] = "Done"
            state["error"] = ""
        else:
            state["status"] = "failed"
            if not state["error"]:
                state["error"] = f"The pipeline exited with status {return_code}."
                if tail:
                    state["error"] += "\n" + "\n".join(tail[-8:])
        state["finished_at"] = _now()
        flush(force=True)
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = f"The pipeline stopped: {exc}"
        state["finished_at"] = _now()
        flush(force=True)
    finally:
        if story_path:
            try:
                os.remove(story_path)
            except OSError:
                pass
        with _lock:
            _job["run_id"] = None
            _job["proc"] = None
            _job["busy"] = False


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class StoryIn(BaseModel):
    story: str = Field(min_length=1, max_length=STORY_MAX_CHARS)


app = FastAPI(title="Story to documents")
recover_interrupted()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session")
def session(site_auth: str | None = Cookie(default=None)):
    if not _site_password():
        return {"ok": False, "detail": "Set SITE_PASSWORD in the server .env."}
    return {"ok": _authorized(site_auth)}


@app.post("/api/login")
def login(body: PasswordIn, response: Response):
    if not _site_password():
        raise HTTPException(status_code=503, detail="Set SITE_PASSWORD in the server .env.")
    if not hmac.compare_digest(body.password, _site_password()):
        raise HTTPException(status_code=401, detail="Wrong password.")
    response.set_cookie(
        COOKIE,
        _auth_token(),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/job")
def current_job(site_auth: str | None = Cookie(default=None)):
    _require(site_auth)
    with _lock:
        run_id = _job["run_id"]
        busy = _job["busy"]
    if not busy:
        return {"run_id": None, "status": "idle"}
    if not run_id:
        return {
            "run_id": None,
            "status": "running",
            "stage": "Starting",
            "files": [],
            "log": "",
            "error": "",
        }
    try:
        payload = _read_status(_run_dir(run_id))
    except HTTPException:
        return {"run_id": run_id, "status": "running", "stage": "Starting", "files": [], "log": "", "error": ""}
    payload["run_id"] = run_id
    payload["status"] = "running"
    return payload


@app.get("/api/runs")
def list_runs(site_auth: str | None = Cookie(default=None)):
    _require(site_auth)
    runs = [_read_status(path) for path in _list_run_dirs()[:30]]
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, site_auth: str | None = Cookie(default=None)):
    _require(site_auth)
    run_dir = _run_dir(run_id)
    payload = _read_status(run_dir)
    payload["story"] = _read_story(run_dir)
    return payload


@app.post("/api/runs")
def start_run(body: StoryIn, site_auth: str | None = Cookie(default=None)):
    _require(site_auth)
    story = body.story.strip()
    if not story:
        raise HTTPException(status_code=400, detail="Enter a refined user story.")
    with _lock:
        if _job["busy"]:
            raise HTTPException(
                status_code=409,
                detail="A run is already in progress. Wait for it to finish.",
            )
        _job["busy"] = True
        _job["run_id"] = None
        _job["proc"] = None
    threading.Thread(target=_run_pipeline, args=(story,), daemon=True).start()
    return {"status": "running"}


@app.get("/api/runs/{run_id}/files/{name}")
def download_file(run_id: str, name: str, site_auth: str | None = Cookie(default=None)):
    _require(site_auth)
    if name not in FILES:
        raise HTTPException(status_code=404, detail="File not found.")
    path = _run_dir(run_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    media = MEDIA_TYPES.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=name)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
