"""
First step of the data collection pipeline: collecting repositories by keyword search.

We store a collection of ~400 words and phrases in Romanian in `./__dictionaries__/keywords.txt`
(and a smaller test suite of around 25 words in `./__dictionaries__/keywords_test.txt`).
We loop through these items, hit the GitHub API endpoints: `GET /search/repositories` and
`GET /search/code` and save the answers.
"""
import time

from constants.constants import (
    TEST_WORDS_PATH,
    SEARCH_REPOS_URL, SEARCH_CODE_URL,
    REPO_CACHE_DIR, CODE_CACHE_DIR,
)
from helpers.cli import parse_args
from helpers.log import setup_logging
from helpers.session import create_session
from helpers.keywords import load_queries
from helpers.gh import search_paginated
from helpers.parsers import parse_repo_item, parse_code_item
from helpers.aggregation import aggregate_and_save


def main():
    args = parse_args()
    log = setup_logging()
    session = create_session()

    words_path = TEST_WORDS_PATH if args.test else args.words
    queries = load_queries(words_path)
    log.info("Loaded %d queries from %s", len(queries), words_path)

    repo_records: list[dict] = []
    code_records: list[dict] = []

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

        try:
            code_items = search_paginated(
                query=query,
                search_url=SEARCH_CODE_URL,
                cache_dir=CODE_CACHE_DIR,
                session=session,
                log=log,
            )
            for item in code_items:
                code_records.append(parse_code_item(item, query))
        except Exception:
            log.exception("Failed code search for q='%s'", query)

        time.sleep(args.delay)

    log.info(
        "Search finished. repo_records=%d, code_records=%d",
        len(repo_records), len(code_records),
    )
    aggregate_and_save(repo_records, code_records, args.output_dir, log)


if __name__ == "__main__":
    main()
