"""
Third search strategy: search /search/issues for Romanian phrases directly
inside PR bodies and comments.
"""
import time
import logging

from pathlib import Path
from requests import Session
from constants.constants import SEARCH_ISSUES_URL, ISSUE_CACHE_DIR, CODE_WORDS_PATH, OUTPUT_DIR
from helpers.keywords import load_queries
from helpers.gh import search_paginated, fetch_repo_meta_cached
from helpers.parsers import parse_repo_item
from helpers.aggregation import save_candidates


def run_issue_search(
    words_path: Path,
    output_dir: Path,
    session: Session,
    log: logging.Logger,
    delay: float = 2.5,
    limit: int | None = None,
) -> list[dict]:
    """Search /search/issues for PRs containing Romanian keywords."""
    queries = load_queries(words_path)
    if limit is not None:
        queries = queries[:limit]
    log.info("INIT       [issue_search] loaded %d queries from %s", len(queries), words_path)

    # Map repo_full_name -> list of matched queries
    repo_queries: dict[str, list[str]] = {}

    for idx, query in enumerate(queries, 1):
        log.info("QUERY      [issue_search %d/%d] q='%s'", idx, len(queries), query)

        try:
            items, cached = search_paginated(
                query=f'"{query}" type:pr',
                search_url=SEARCH_ISSUES_URL,
                cache_dir=ISSUE_CACHE_DIR,
                session=session,
                log=log,
            )
            for item in items:
                # Extract repo full_name from repository_url
                # Format: https://api.github.com/repos/{owner}/{repo}
                repo_url = item.get("repository_url", "")
                full_name = "/".join(repo_url.rstrip("/").split("/")[-2:])
                if full_name:
                    repo_queries.setdefault(full_name, []).append(query)
        except Exception:
            log.exception("ERROR      [issue_search %d/%d] failed q='%s'", idx, len(queries), query)
            cached = False

        if not cached:
            time.sleep(delay)

    log.info("INIT       [repo_meta] fetching metadata for %d unique repos", len(repo_queries))

    # For each unique repo: fetch repo info, PR count, contributor info
    total = len(repo_queries)
    records: list[dict] = []
    for i, (full_name, matched) in enumerate(sorted(repo_queries.items()), 1):
        meta = fetch_repo_meta_cached(full_name, session, log,
                                      progress=(i, total))
        repo_data = meta.get("repo_info")
        if repo_data is None:
            log.warning("SKIP       [repo_meta %d/%d] %s — could not fetch repo info", i, total, full_name)
            continue

        for query in matched:
            record = parse_repo_item(repo_data, query)
            record["total_pr_count"] = meta.get("total_pr_count")
            record["total_contributors"] = meta.get("total_contributors")
            record["human_contributors"] = meta.get("human_contributors")
            records.append(record)

    log.info("DONE       [issue_search] %d records, %d unique repos", len(records), len(repo_queries))
    save_candidates(records, output_dir, "issue_search_candidates.json", log)
    return records
