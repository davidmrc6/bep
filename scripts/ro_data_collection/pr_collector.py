"""
Collect PR discussion text from filtered candidate repos.

For each repo in filtered_candidates.json:
1. List all PRs (state=all)
2. For each PR, fetch:
   - Issue comments (general discussion on the PR)
   - Review comments (inline code review)
   - Reviews (approve/reject bodies)
3. Filter out bot authors
4. Save all human comment text with metadata

Output: one JSON file per repo in the cache dir (for resumability),
plus a combined pr_comments.json in the output dir.
"""
import json
import logging

from pathlib import Path
from requests import Session
from constants.constants import OUTPUT_DIR, PR_CACHE_DIR
from helpers.gh import paginate_core, _is_human
from helpers.aggregation import load_json, _save_json


def _repo_cache_path(full_name: str) -> Path:
    slug = full_name.replace("/", "__")
    return PR_CACHE_DIR / slug / "comments.json"


def _repo_is_cached(full_name: str) -> bool:
    return _repo_cache_path(full_name).exists()


def _save_repo_cache(full_name: str, comments: list[dict]) -> None:
    _save_json(comments, _repo_cache_path(full_name))


def _load_repo_cache(full_name: str) -> list[dict]:
    return load_json(_repo_cache_path(full_name))


def _is_human_comment(author_login: str, author_type: str) -> bool:
    """Reuse the bot detection from gh.py via the _is_human helper."""
    return _is_human({"login": author_login, "type": author_type})


def _parse_comment(raw: dict, repo_full_name: str, pr_number: int,
                   pr_url: str, pr_title: str, comment_type: str) -> dict | None:
    """Parse a raw comment/review into a flat record. Returns None for bots or empty bodies."""
    body = (raw.get("body") or "").strip()
    if not body:
        return None

    author = raw.get("user") or {}
    login = author.get("login", "")
    atype = author.get("type", "User")

    if not _is_human_comment(login, atype):
        return None

    return {
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "pr_url": pr_url,
        "comment_type": comment_type,
        "author_login": login,
        "body": body,
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def collect_repo_comments(full_name: str, session: Session, log: logging.Logger) -> list[dict]:
    """Collect all human PR discussion text for a single repo."""
    # List all PRs
    pulls_url = f"https://api.github.com/repos/{full_name}/pulls"
    all_prs = paginate_core(pulls_url, session, log, params={"state": "all"})

    log.info("INFO       [pr_collect] %s: %d PRs total", full_name, len(all_prs))

    comments: list[dict] = []

    for pr in all_prs:
        pr_number = pr["number"]
        pr_title = pr.get("title", "")
        pr_url = pr.get("html_url", "")

        # Issue comments (general PR discussion)
        issue_comments_url = f"https://api.github.com/repos/{full_name}/issues/{pr_number}/comments"
        for raw in paginate_core(issue_comments_url, session, log):
            rec = _parse_comment(raw, full_name, pr_number, pr_url, pr_title, "issue_comment")
            if rec:
                comments.append(rec)

        # Review comments (inline code review)
        review_comments_url = f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/comments"
        for raw in paginate_core(review_comments_url, session, log):
            rec = _parse_comment(raw, full_name, pr_number, pr_url, pr_title, "review_comment")
            if rec:
                comments.append(rec)

        # Reviews (approve/reject with body text)
        reviews_url = f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/reviews"
        for raw in paginate_core(reviews_url, session, log):
            rec = _parse_comment(raw, full_name, pr_number, pr_url, pr_title, "review")
            if rec:
                comments.append(rec)

    return comments


def run_pr_collector(
    input_path: Path,
    output_path: Path,
    session: Session,
    log: logging.Logger,
    limit: int | None = None,
) -> list[dict]:
    """Collect PR comments for all repos in input_path. Returns all comments."""
    repos = load_json(input_path, log)
    if limit is not None:
        repos = repos[:limit]
    log.info("INIT       [pr_collect] processing %d repos from %s", len(repos), input_path)

    all_comments: list[dict] = []

    for i, repo in enumerate(repos, 1):
        full_name = repo["repo_full_name"]

        # Check cache
        if _repo_is_cached(full_name):
            cached = _load_repo_cache(full_name)
            log.info("CACHE HIT  [pr_collect %d/%d] %s (%d comments)", i, len(repos), full_name, len(cached))
            all_comments.extend(cached)
            continue

        log.info("FETCH      [pr_collect %d/%d] %s", i, len(repos), full_name)
        try:
            comments = collect_repo_comments(full_name, session, log)
        except Exception:
            log.exception("ERROR      [pr_collect %d/%d] failed %s", i, len(repos), full_name)
            comments = []

        _save_repo_cache(full_name, comments)
        all_comments.extend(comments)
        log.info("DONE       [pr_collect %d/%d] %s → %d human comments", i, len(repos), full_name, len(comments))

    # Save combined output
    _save_json(all_comments, output_path)

    unique_repos = len({c["repo_full_name"] for c in all_comments})
    unique_prs = len({(c["repo_full_name"], c["pr_number"]) for c in all_comments})
    log.info("DONE       [pr_collect] %d comments from %d PRs across %d repos", len(all_comments), unique_prs, unique_repos)

    return all_comments


if __name__ == "__main__":
    import argparse
    from helpers.log import setup_logging
    from helpers.session import create_session

    p = argparse.ArgumentParser(description="Collect PR comments from filtered repos")
    p.add_argument(
        "--input", type=Path,
        default=OUTPUT_DIR / "filtered_candidates.json",
        help="Path to filtered candidates JSON",
    )
    p.add_argument(
        "--output", type=Path,
        default=OUTPUT_DIR / "pr_comments.json",
        help="Path to write collected comments",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N repos (for testing)",
    )
    args = p.parse_args()

    run_pr_collector(
        input_path=args.input,
        output_path=args.output,
        session=create_session(),
        log=setup_logging(),
        limit=args.limit,
    )
