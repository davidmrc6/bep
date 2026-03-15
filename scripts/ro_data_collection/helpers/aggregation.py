import json
import logging

from pathlib import Path


def _save_json(records: list[dict], path: Path) -> None:
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False))


def save_candidates(
    records: list[dict],
    output_dir: Path,
    filename: str,
    log: logging.Logger,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    _save_json(records, path)
    log.info("Saved %d records to %s", len(records), path.resolve())

    unique_repos = len({r["repo_full_name"] for r in records})
    print(f"\n{'='*60}")
    print(f"Total records          : {len(records):>6}")
    print(f"Unique repos           : {unique_repos:>6}")
    print(f"{'='*60}")