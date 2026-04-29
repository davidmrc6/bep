"""
First step of the data collection pipeline: collecting repositories by keyword search.

Keywords from keywords_repo.txt are searched via GET /search/repositories,
then PR count and contributor info are fetched for each unique repo found.
"""
import time
import logging

from pathlib import Path
from requests import Session
from constants.constants import SEARCH_REPOS_URL, REPO_CACHE_DIR
from helpers.keywords import load_queries
from helpers.gh import search_paginated, fetch_repo_meta_cached
from helpers.parsers import parse_repo_item
from helpers.aggregation import save_candidates


def run_repo_search(
    words_path: Path,
    output_dir: Path,
    session: Session,
    log: logging.Logger,
    delay: float = 2.5,
    limit: int | None = None,
) -> list[dict]:
    """Run the repo keyword search and return the collected records."""
    queries = load_queries(words_path)
    if limit is not None:
        queries = queries[:limit]
    log.info("INIT       [repo_search] loaded %d queries from %s", len(queries), words_path)

    repo_records: list[dict] = []

    for idx, query in enumerate(queries, 1):
        log.info("QUERY      [repo_search %d/%d] q='%s'", idx, len(queries), query)

        try:
            repo_items, cached = search_paginated(
                query=query,
                search_url=SEARCH_REPOS_URL,
                cache_dir=REPO_CACHE_DIR,
                extra_params={"sort": "updated", "order": "desc"},
                session=session,
                log=log,
            )
            for item in repo_items:
                repo_records.append(parse_repo_item(item, query))
        except Exception:
            log.exception("ERROR      [repo_search %d/%d] failed q='%s'", idx, len(queries), query)
            cached = False

        if not cached:
            time.sleep(delay)

    # Fetch PR counts and contributor info for each unique repo (core rate limit)
    unique_repos = sorted({r["repo_full_name"] for r in repo_records})
    log.info("INIT       [repo_meta] fetching metadata for %d unique repos", len(unique_repos))

    total = len(unique_repos)
    repo_meta: dict[str, dict] = {}
    for i, full_name in enumerate(unique_repos, 1):
        repo_meta[full_name] = fetch_repo_meta_cached(full_name, session, log,
                                                       progress=(i, total))

    # Attach metadata to all records
    for r in repo_records:
        meta = repo_meta.get(r["repo_full_name"], {})
        r["total_pr_count"] = meta.get("total_pr_count")
        r["total_contributors"] = meta.get("total_contributors")
        r["human_contributors"] = meta.get("human_contributors")

    log.info("DONE       [repo_search] %d records, %d unique repos", len(repo_records), len(unique_repos))
    save_candidates(repo_records, output_dir, "repo_search_candidates.json", log)
    return repo_records
