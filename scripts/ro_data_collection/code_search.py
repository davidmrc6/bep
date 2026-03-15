"""
Second search strategy: find repos via code search.

Keywords here are phrases unlikely to appear in repo descriptions but likely
in code comments, PR bodies, etc. (e.g. "te rog modifica").
For each unique repo discovered, we fetch full repo metadata, PR count,
and contributor info — producing the same record format as repo_search.py.
"""
import time

from constants.constants import (
    TEST_WORDS_PATH,
    SEARCH_CODE_URL,
    CODE_CACHE_DIR,
)
from helpers.cli import parse_code_search_args
from helpers.log import setup_logging
from helpers.session import create_session
from helpers.keywords import load_queries
from helpers.gh import (
    search_paginated,
    fetch_repo_info,
    fetch_total_pr_count,
    fetch_contributor_info,
)
from helpers.parsers import parse_repo_item
from helpers.aggregation import save_candidates


def main():
    args = parse_code_search_args()
    log = setup_logging()
    session = create_session()

    words_path = args.words
    queries = load_queries(words_path)
    if args.limit is not None:
        queries = queries[:args.limit]
    log.info("Loaded %d queries from %s", len(queries), words_path)

    # Map repo_full_name -> list of matched queries
    repo_queries: dict[str, list[str]] = {}

    for idx, query in enumerate(queries, 1):
        log.info("--- Query %d/%d: '%s' ---", idx, len(queries), query)

        try:
            code_items = search_paginated(
                query=query,
                search_url=SEARCH_CODE_URL,
                cache_dir=CODE_CACHE_DIR,
                session=session,
                log=log,
            )
            for item in code_items:
                repo = item.get("repository", {})
                full_name = repo.get("full_name")
                if full_name:
                    repo_queries.setdefault(full_name, []).append(query)
        except Exception:
            log.exception("Failed code search for q='%s'", query)

        time.sleep(args.delay)

    log.info("Code search found %d unique repos. Fetching metadata...", len(repo_queries))

    # For each unique repo: fetch repo info, PR count, contributor info
    records: list[dict] = []
    for i, (full_name, matched) in enumerate(sorted(repo_queries.items()), 1):
        if i % 50 == 0:
            log.info("Metadata progress: %d/%d", i, len(repo_queries))

        repo_data = fetch_repo_info(full_name, session, log)
        if repo_data is None:
            log.warning("Skipping %s — could not fetch repo info", full_name)
            continue

        pr_count = fetch_total_pr_count(full_name, session, log)
        contrib_info = fetch_contributor_info(full_name, session, log)

        # One record per matched query
        for query in matched:
            record = parse_repo_item(repo_data, query)
            record["total_pr_count"] = pr_count
            record["total_contributors"] = contrib_info.get("total_contributors")
            record["human_contributors"] = contrib_info.get("human_contributors")
            records.append(record)

    log.info("Code search finished. %d records, %d unique repos", len(records), len(repo_queries))
    save_candidates(records, args.output_dir, "code_search_candidates.json", log)


if __name__ == "__main__":
    main()