import json
import logging
import tempfile

from pathlib import Path


def _save_json(records: list[dict], path: Path) -> None:
    """Atomically write JSON: write to temp file then rename, so a crash mid-write
    doesn't corrupt the output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        Path(tmp_path).replace(path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def load_json(path: Path, log: logging.Logger | None = None) -> list[dict]:
    """Safely load a JSON list from a file. Returns [] if missing or corrupt."""
    if not path.exists():
        if log:
            log.warning("WARN       [io] file not found: %s — returning empty list", path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if log:
            log.warning("WARN       [io] expected list in %s, got %s — returning empty", path, type(data).__name__)
        return []
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if log:
            log.warning("WARN       [io] corrupt JSON in %s: %s — returning empty list", path, exc)
        return []


def save_candidates(
    records: list[dict],
    output_dir: Path,
    filename: str,
    log: logging.Logger,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    _save_json(records, path)
    log.info("SAVE       [io] %d records → %s", len(records), path.resolve())

    unique_repos = len({r["repo_full_name"] for r in records})
    print(f"\n{'='*60}")
    print(f"Total records          : {len(records):>6}")
    print(f"Unique repos           : {unique_repos:>6}")
    print(f"{'='*60}")