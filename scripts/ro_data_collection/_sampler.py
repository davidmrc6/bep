"""
Stratified sample for the Romanian gold standard.

Caps: 30 per repo, 20 per author, 8 per PR, 250 per year.
Floor: at least 200 `review` entries (the rest is `review_comment`).

Two-pass shuffle: fill the review floor first, then top up with review_comment
up to the target N
"""
import argparse
import logging
import random

from collections import Counter
from pathlib import Path

from constants.constants import OUTPUT_DIR
from helpers.aggregation import load_json, _save_json


DEFAULT_TARGET = 2000
DEFAULT_SEED = 42

CAP_PER_REPO = 30
CAP_PER_AUTHOR = 20
CAP_PER_PR = 8
CAP_PER_YEAR = 250
REVIEW_FLOOR = 200


def _year_of(entry: dict) -> str | None:
    ts = entry.get("created_at")
    return ts[:4] if ts else None


def _try_admit(entry: dict, counts: dict) -> bool:
    repo = entry["repo_full_name"]
    author = entry["author_login"]
    pr_key = (repo, entry["pr_number"])
    year = _year_of(entry)

    if counts["repo"][repo] >= CAP_PER_REPO:
        return False
    if counts["author"][author] >= CAP_PER_AUTHOR:
        return False
    if counts["pr"][pr_key] >= CAP_PER_PR:
        return False
    if year is not None and counts["year"][year] >= CAP_PER_YEAR:
        return False

    counts["repo"][repo] += 1
    counts["author"][author] += 1
    counts["pr"][pr_key] += 1
    if year is not None:
        counts["year"][year] += 1
    return True


def _sample_pool(pool: list[dict], counts: dict, limit: int,
                 accepted: list[dict], rng: random.Random) -> None:
    rng.shuffle(pool)
    start = len(accepted)
    for e in pool:
        if len(accepted) - start >= limit:
            break
        if _try_admit(e, counts):
            accepted.append(e)


def _percentile(arr: list, p: float):
    return arr[int(len(arr) * p)] if arr else 0


def _top_share(c: Counter, k: int) -> float:
    total = sum(c.values())
    return sum(n for _, n in c.most_common(k)) / total if total else 0.0


def _stats(sample: list[dict]) -> dict:
    repos = Counter(e["repo_full_name"] for e in sample)
    authors = Counter(e["author_login"] for e in sample)
    prs = Counter((e["repo_full_name"], e["pr_number"]) for e in sample)
    years = Counter(_year_of(e) for e in sample if _year_of(e))
    types = Counter(e["comment_type"] for e in sample)
    lens = sorted(len(e["body"]) for e in sample)
    code_ratios = sorted(float(e.get("code_ratio", 0.0)) for e in sample)
    has_email = sum(1 for e in sample if e.get("has_email"))

    return {
        "n": len(sample),
        "distinct_repos": len(repos),
        "distinct_authors": len(authors),
        "distinct_prs": len(prs),
        "distinct_years": len(years),
        "top10_share_repo": round(_top_share(repos, 10), 4),
        "top10_share_author": round(_top_share(authors, 10), 4),
        "top3_share_year": round(_top_share(years, 3), 4),
        "comment_type_breakdown": dict(types),
        "year_breakdown": dict(sorted(years.items())),
        "body_length": {
            "min": lens[0] if lens else 0,
            "p25": _percentile(lens, 0.25),
            "median": _percentile(lens, 0.5),
            "p75": _percentile(lens, 0.75),
            "p90": _percentile(lens, 0.90),
            "max": lens[-1] if lens else 0,
        },
        "code_ratio": {
            "median": _percentile(code_ratios, 0.5),
            "p90": _percentile(code_ratios, 0.90),
        },
        "has_email_count": has_email,
    }


def run_sampler(
    input_path: Path,
    output_path: Path,
    stats_path: Path,
    log: logging.Logger,
    target: int = DEFAULT_TARGET,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    entries = load_json(input_path, log)
    log.info("LOAD       [sampler] %d entries from %s", len(entries), input_path)

    rng = random.Random(seed)
    counts = {
        "repo": Counter(),
        "author": Counter(),
        "pr": Counter(),
        "year": Counter(),
    }
    accepted: list[dict] = []

    reviews = [e for e in entries if e.get("comment_type") == "review"]
    review_comments = [e for e in entries if e.get("comment_type") == "review_comment"]
    log.info("INFO       [sampler] pools: %d review, %d review_comment",
             len(reviews), len(review_comments))

    _sample_pool(reviews, counts, REVIEW_FLOOR, accepted, rng)
    log.info("INFO       [sampler] after review pass: %d sampled", len(accepted))

    remaining = max(target - len(accepted), 0)
    _sample_pool(review_comments, counts, remaining, accepted, rng)
    log.info("INFO       [sampler] after review_comment pass: %d sampled", len(accepted))

    if len(accepted) < target:
        log.warning("WARN       [sampler] only sampled %d of %d (caps limit)",
                    len(accepted), target)

    _save_json(accepted, output_path)
    log.info("SAVE       [sampler] %d entries → %s", len(accepted), output_path)

    stats = _stats(accepted)
    _save_json(stats, stats_path)
    log.info("SAVE       [sampler] stats → %s", stats_path)

    log.info("INFO       [sampler] %d repos, %d authors, %d PRs, %d years",
             stats["distinct_repos"], stats["distinct_authors"],
             stats["distinct_prs"], stats["distinct_years"])
    log.info("INFO       [sampler] top-10 share: repo=%.1f%% author=%.1f%%; top-3 year=%.1f%%",
             100 * stats["top10_share_repo"],
             100 * stats["top10_share_author"],
             100 * stats["top3_share_year"])
    log.info("INFO       [sampler] type breakdown: %s", stats["comment_type_breakdown"])

    return accepted
