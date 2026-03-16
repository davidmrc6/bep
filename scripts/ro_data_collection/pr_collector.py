"""
Collect PR discussion text from filtered candidate repos.

For each repo in filtered_candidates.json:
1. List all PRs (state=all)
2. For PRs that have comments (comments + review_comments > 0):
   - Fetch issue comments (general discussion on the PR)
   - Fetch review comments (inline code review)
   - Fetch reviews (approve/reject bodies)
3. Filter out bot authors
4. Save all human comment text with metadata

Output: one JSON file per repo in the cache dir (for resumability),
plus a combined pr_comments.json in the output dir.
"""
import argparse
import json

from pathlib import Path
from constants.constants import OUTPUT_DIR, PR_CACHE_DIR
from helpers.log import setup_logging
from helpers.session import create_session
from helpers.gh import paginate_core, _is_human


def load_filtered(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_cache_path(full_name: str) -> Path:
    slug = full_name.replace("/", "__")
    return PR_CACHE_DIR / slug / "comments.json"


def _repo_is_cached(full_name: str) -> bool:
    return _repo_cache_path(full_name).exists()


def _save_repo_cache(full_name: str, comments: list[dict]) -> None:
    path = _repo_cache_path(full_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comments, indent=2, ensure_ascii=False))


def _load_repo_cache(full_name: str) -> list[dict]:
    return json.loads(_repo_cache_path(full_name).read_text(encoding="utf-8"))


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


def collect_repo_comments(full_name: str, session, log) -> list[dict]:
    """Collect all human PR discussion text for a single repo."""
    # List all PRs
    pulls_url = f"https://api.github.com/repos/{full_name}/pulls"
    all_prs = paginate_core(pulls_url, session, log, params={"state": "all"})

    log.info("  %s: %d PRs total", full_name, len(all_prs))

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


def main():
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

    log = setup_logging()
    session = create_session()

    repos = load_filtered(args.input)
    if args.limit is not None:
        repos = repos[:args.limit]
    log.info("Processing %d repos from %s", len(repos), args.input)

    all_comments: list[dict] = []

    for i, repo in enumerate(repos, 1):
        full_name = repo["repo_full_name"]

        # Check cache
        if _repo_is_cached(full_name):
            cached = _load_repo_cache(full_name)
            log.info("[%d/%d] CACHE HIT  %s (%d comments)", i, len(repos), full_name, len(cached))
            all_comments.extend(cached)
            continue

        log.info("[%d/%d] Collecting  %s", i, len(repos), full_name)
        try:
            comments = collect_repo_comments(full_name, session, log)
        except Exception:
            log.exception("Failed to collect %s", full_name)
            comments = []

        _save_repo_cache(full_name, comments)
        all_comments.extend(comments)
        log.info("  → %d human comments collected", len(comments))

    # Save combined output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(all_comments, indent=2, ensure_ascii=False))

    unique_repos = len({c["repo_full_name"] for c in all_comments})
    unique_prs = len({(c["repo_full_name"], c["pr_number"]) for c in all_comments})
    log.info("Done. %d comments from %d PRs across %d repos", len(all_comments), unique_prs, unique_repos)

    print(f"\n{'='*60}")
    print(f"Total human comments   : {len(all_comments):>6}")
    print(f"Unique PRs with text   : {unique_prs:>6}")
    print(f"Unique repos           : {unique_repos:>6}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()