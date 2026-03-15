"""
First step of the data collection pipeline: collecting repositories by keyword search.

We store a collection of ~400 words and phrases in Romanian in `./__dictionaries__/keywords.txt`
(and a smaller test suite of around 25 words in `./__dictionaries__/keywords_test.txt`).
We loop through these items, hit the GitHub API endpoint `GET /search/repositories`,
then fetch the total PR count for each unique repo found.
"""
import time

from constants.constants import (
    TEST_WORDS_PATH,
    SEARCH_REPOS_URL,
    REPO_CACHE_DIR,
)
from helpers.cli import parse_repo_search_args
from helpers.log import setup_logging
from helpers.session import create_session
from helpers.keywords import load_queries
from helpers.gh import search_paginated, fetch_total_pr_count, fetch_contributor_info
from helpers.parsers import parse_repo_item
from helpers.aggregation import save_candidates


def main():
    args = parse_repo_search_args()
    log = setup_logging()
    session = create_session()

    words_path = args.words
    queries = load_queries(words_path)
    if args.limit is not None:
        queries = queries[:args.limit]
    log.info("Loaded %d queries from %s", len(queries), words_path)

    repo_records: list[dict] = []

    for idx, query in enumerate(queries, 1):
        log.info("--- Query %d/%d: '%s' ---", idx, len(queries), query)

        try:
            repo_items = search_paginated(
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
            log.exception("Failed repo search for q='%s'", query)

        time.sleep(args.delay)

    # Fetch PR counts and contributor info for each unique repo (core rate limit)
    unique_repos = sorted({r["repo_full_name"] for r in repo_records})
    log.info("Fetching PR counts and contributor info for %d unique repos...", len(unique_repos))

    repo_meta: dict[str, dict] = {}
    for i, full_name in enumerate(unique_repos, 1):
        if i % 50 == 0:
            log.info("Metadata progress: %d/%d", i, len(unique_repos))
        pr_count = fetch_total_pr_count(full_name, session, log)
        contrib_info = fetch_contributor_info(full_name, session, log)
        repo_meta[full_name] = {"total_pr_count": pr_count, **contrib_info}

    # Attach metadata to all records
    for r in repo_records:
        meta = repo_meta.get(r["repo_full_name"], {})
        r["total_pr_count"] = meta.get("total_pr_count")
        r["total_contributors"] = meta.get("total_contributors")
        r["human_contributors"] = meta.get("human_contributors")

    log.info("Search finished. %d records, %d unique repos", len(repo_records), len(unique_repos))
    save_candidates(repo_records, args.output_dir, "repo_search_candidates.json", log)


if __name__ == "__main__":
    main()