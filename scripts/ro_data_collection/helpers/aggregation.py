import json
import logging

from pathlib import Path
import pandas as pd


def _dedup_candidates(
    records: list[dict],
    log: logging.Logger,
    label: str,
) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        log.info("No %s candidates collected.", label)
        return df

    query_agg = (
        df.groupby("repo_full_name")["matched_query"]
        .apply(lambda qs: "; ".join(sorted(set(qs))))
        .rename("matched_queries")
    )
    dedup = (
        df.drop_duplicates(subset="repo_full_name", keep="first")
        .drop(columns=["matched_query"])
        .merge(query_agg, on="repo_full_name")
    )
    log.info("%s candidates: %d raw → %d unique repos", label, len(df), len(dedup))
    return dedup


def _save_json(df: pd.DataFrame, path: Path) -> None:
    records = df.where(df.notna(), None).to_dict(orient="records")
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False))


def aggregate_and_save(
    repo_records: list[dict],
    code_records: list[dict],
    output_dir: Path,
    log: logging.Logger,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    df_repo = _dedup_candidates(repo_records, log, "Repo")
    df_code = _dedup_candidates(code_records, log, "Code")

    _save_json(df_repo, output_dir / "repo_search_candidates.json")
    _save_json(df_code, output_dir / "code_search_candidates.json")

    # Combined file
    df_all = pd.concat([df_repo, df_code], ignore_index=True)
    unique_repos = df_all["repo_full_name"].nunique() if not df_all.empty else 0
    log.info("Total unique candidate repos (all sources): %d", unique_repos)

    _save_json(df_all, output_dir / "all_candidates.json")

    log.info("Outputs written to %s", output_dir.resolve())
    print(f"\n{'='*60}")
    print(f"Repo search candidates : {len(df_repo):>6}")
    print(f"Code search candidates : {len(df_code):>6}")
    print(f"All candidates         : {len(df_all):>6}")
    print(f"Unique repos           : {unique_repos:>6}")
    print(f"{'='*60}")
