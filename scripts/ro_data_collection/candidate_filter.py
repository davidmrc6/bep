"""
Post-processing step: takes the raw candidates from repo_search and code_search,
and filters/cleans them before further analysis.

Steps:
1. Merge duplicate repos (combine their matched_query fields)
2. Remove repos with too few total PRs
3. Remove repos that are too large (by stars or PR count) — likely big projects
   where Romanian is incidental
4. Remove repos with fewer than 2 human contributors
5. Remove translation/i18n/l10n repos where Romanian is just one of many languages
"""
import argparse
import json
import logging
import re

from pathlib import Path
from constants.constants import OUTPUT_DIR
from helpers.aggregation import load_json, _save_json

DEFAULT_MIN_PRS = 5
DEFAULT_MAX_PRS = 1000
DEFAULT_MAX_STARS = 2000
DEFAULT_MIN_HUMAN_CONTRIBUTORS = 2

# Patterns that indicate a repo is a translation/i18n/docs-translation project
_I18N_PATTERNS = re.compile(
    r"i18n|l10n|\blocales?\b|\blocali[zs]ation\b"
    r"|\btranslat(e|ion|ions|ing|or)\b"
    r"|crowdin|transifex|weblate|pontoon"
    r"|\blang(uage)?[\-_]?pack"
    r"|-ro\b|[\-_]ro\b|romanian[\-_]translation",
    re.IGNORECASE,
)

# Topic keywords that signal translation repos
_I18N_TOPICS = {
    "i18n", "l10n", "localization", "localisation", "translation",
    "translations", "crowdin", "transifex", "weblate", "internationalization",
}


def load_candidates(path: Path, log: logging.Logger | None = None) -> list[dict]:
    return load_json(path, log)


def merge_duplicates(records: list[dict]) -> list[dict]:
    """Merge records for the same repo, combining matched_query values."""
    by_repo: dict[str, dict] = {}
    for r in records:
        name = r["repo_full_name"]
        if name not in by_repo:
            by_repo[name] = {**r, "matched_queries": [r["matched_query"]]}
            del by_repo[name]["matched_query"]
        else:
            by_repo[name]["matched_queries"].append(r["matched_query"])

    # Deduplicate query lists
    for entry in by_repo.values():
        entry["matched_queries"] = sorted(set(entry["matched_queries"]))

    return list(by_repo.values())


def _looks_like_i18n(repo: dict) -> bool:
    """Heuristic: does this repo look like a translation/i18n/l10n project?"""
    # Check repo name
    full_name = repo.get("repo_full_name", "")
    if _I18N_PATTERNS.search(full_name):
        return True

    # Check description
    desc = repo.get("description") or ""
    if _I18N_PATTERNS.search(desc):
        return True

    # Check topics
    topics_str = repo.get("topics") or ""
    topics = {t.strip().lower() for t in topics_str.split(",") if t.strip()}
    if topics & _I18N_TOPICS:
        return True

    return False


def filter_candidates(
    records: list[dict],
    min_prs: int,
    max_prs: int,
    max_stars: int,
    min_human_contributors: int,
) -> list[dict]:
    filtered = []
    for r in records:
        pr_count = r.get("total_pr_count")
        stars = r.get("stargazers_count", 0)
        human_contribs = r.get("human_contributors")

        # Skip repos where we couldn't fetch PR count
        if pr_count is None:
            continue

        if pr_count < min_prs:
            continue

        if pr_count > max_prs:
            continue

        if stars > max_stars:
            continue

        # Require at least N human contributors
        if human_contribs is not None and human_contribs < min_human_contributors:
            continue

        # Skip translation/i18n repos
        if _looks_like_i18n(r):
            continue

        filtered.append(r)

    return filtered


def run_candidate_filter(
    input_paths: list[Path],
    output_path: Path,
    log: logging.Logger,
    min_prs: int = DEFAULT_MIN_PRS,
    max_prs: int = DEFAULT_MAX_PRS,
    max_stars: int = DEFAULT_MAX_STARS,
    min_human_contributors: int = DEFAULT_MIN_HUMAN_CONTRIBUTORS,
) -> list[dict]:
    """Load, merge, filter candidates. Returns the filtered list."""
    raw = []
    for input_path in input_paths:
        records = load_candidates(input_path, log)
        log.info("LOAD       [filter] %d records from %s", len(records), input_path.name)
        raw.extend(records)
    log.info("INFO       [filter] %d raw records total", len(raw))

    merged = merge_duplicates(raw)
    log.info("INFO       [filter] %d unique repos after dedup", len(merged))

    i18n_count = sum(1 for r in merged if _looks_like_i18n(r))
    log.info("INFO       [filter] %d i18n/translation repos detected", i18n_count)

    filtered = filter_candidates(merged, min_prs, max_prs, max_stars, min_human_contributors)
    log.info(
        "DONE       [filter] %d repos after filtering (prs: %d-%d, stars: <=%d, human contributors: >=%d)",
        len(filtered), min_prs, max_prs, max_stars, min_human_contributors,
    )

    _save_json(filtered, output_path)
    log.info("SAVE       [filter] written to %s", output_path.resolve())
    return filtered


if __name__ == "__main__":
    from helpers.log import setup_logging

    p = argparse.ArgumentParser(description="Filter and deduplicate repo candidates")
    p.add_argument(
        "--input", type=Path, nargs="+",
        default=[
            OUTPUT_DIR / "repo_search_candidates.json",
            OUTPUT_DIR / "code_search_candidates.json",
            OUTPUT_DIR / "issue_search_candidates.json",
        ],
        help="Path(s) to raw candidates JSON files",
    )
    p.add_argument(
        "--output", type=Path,
        default=OUTPUT_DIR / "filtered_candidates.json",
        help="Path to write filtered output",
    )
    p.add_argument("--min-prs", type=int, default=DEFAULT_MIN_PRS)
    p.add_argument("--max-prs", type=int, default=DEFAULT_MAX_PRS)
    p.add_argument("--max-stars", type=int, default=DEFAULT_MAX_STARS)
    p.add_argument("--min-human-contributors", type=int, default=DEFAULT_MIN_HUMAN_CONTRIBUTORS)
    args = p.parse_args()

    run_candidate_filter(
        input_paths=args.input,
        output_path=args.output,
        log=setup_logging(),
        min_prs=args.min_prs,
        max_prs=args.max_prs,
        max_stars=args.max_stars,
        min_human_contributors=args.min_human_contributors,
    )
