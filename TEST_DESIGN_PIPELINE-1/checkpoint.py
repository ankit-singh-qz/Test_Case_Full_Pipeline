"""Per-tier checkpointing, so a run killed part-way is resumable.

Twenty LLM calls sit behind one `python main.py`. Before this, a Bedrock
outage during tier 3 threw away tiers 1 and 2 as well, and the next
attempt paid for all of them again -- which is what made an hour of 503s
so expensive. Each tier's merged state is now written to
output/.checkpoint.json as it completes, and a later run with the SAME
inputs replays those tiers from disk instead of calling the model.

The file is keyed by a hash of the two input handoff files. Point the
pipeline at a different FDD or TDD state and the key changes, so a stale
checkpoint can never be mistaken for this run's work. Delete
output/.checkpoint.json (or pass --fresh to main.py) to force a full
re-run against unchanged inputs.
"""
import hashlib
import json
import os

CHECKPOINT_PATH = os.path.join("output", ".checkpoint.json")
FORMAT_VERSION = 1


def input_key(*paths: str) -> str:
    """A stable id for this combination of input files, from their
    contents rather than their paths -- two runs pointed at differently
    named copies of the same state should share a checkpoint, and one
    pointed at an edited file should not."""
    digest = hashlib.sha256()
    digest.update(f"v{FORMAT_VERSION}".encode("utf-8"))
    for path in paths:
        digest.update(b"\0")
        try:
            with open(path, "rb") as handle:
                digest.update(handle.read())
        except OSError:
            digest.update(os.path.abspath(path).encode("utf-8"))
    return digest.hexdigest()[:16]


def _read() -> dict:
    try:
        with open(CHECKPOINT_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load(key: str) -> dict:
    """Every tier already completed for this key, as {tier: state_update}.
    Empty when there is nothing to resume."""
    if not key:
        return {}
    data = _read()
    if data.get("key") != key:
        return {}
    tiers = data.get("tiers")
    return tiers if isinstance(tiers, dict) else {}


def record(key: str, tier: str, state_update: dict) -> None:
    """Append one finished tier. A checkpoint for different inputs is
    replaced outright rather than merged into."""
    if not key:
        return
    data = _read()
    if data.get("key") != key:
        data = {"key": key, "tiers": {}}
    tiers = data.setdefault("tiers", {})
    tiers[tier] = state_update

    os.makedirs(os.path.dirname(CHECKPOINT_PATH) or ".", exist_ok=True)
    temp_path = CHECKPOINT_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(temp_path, CHECKPOINT_PATH)


def clear() -> None:
    """Drop the checkpoint. Called once a run assembles successfully, so
    the next run starts clean."""
    try:
        os.remove(CHECKPOINT_PATH)
    except OSError:
        pass
