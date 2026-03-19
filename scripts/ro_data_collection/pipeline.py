"""
Runs the full data collection pipeline.
"""
import argparse

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from constants.constants import (
    REPO_WORDS_PATH, CODE_WORDS_PATH, OUTPUT_DIR,
)
from helpers.log import setup_logging
from helpers.session import create_session

from repo_search import run_repo_search
from code_search import run_code_search
from candidate_filter import run_candidate_filter
from pr_collector import run_pr_collector
from lang_filter import run_lang_filter


def main():
    p = argparse.ArgumentParser(description="Run the full Romanian data collection pipeline")
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--delay", type=float, default=2.5)
    p.add_argument("--limit", type=int, default=None, help="Limit keywords per search stage")
    p.add_argument("--pr-limit", type=int, default=None, help="Limit repos for PR collection")
    p.add_argument(
        "--parallel-search", action="store_true",
        help="Run repo and code search in parallel (requires GH_TOKEN_REPO and GH_TOKEN_CODE env vars)",
    )
    p.add_argument(
        "--skip-search", action="store_true",
        help="Skip search stages, start from filtering",
    )
    p.add_argument(
        "--skip-to-lang", action="store_true",
        help="Skip everything before language filtering",
    )
    args = p.parse_args()

    log = setup_logging()
    out = args.output_dir

    # Repository/Code Search
    if not args.skip_search and not args.skip_to_lang:
        if args.parallel_search:
            # If the `parallel_search` argument is passed, run repo search and code search
            # in two parallel threads with different GitHub API keys to make the search
            # faster.
            log.info("=== Stage 1 & 2: Parallel repo + code search ===")
            session_repo = create_session(token_env="GH_TOKEN_REPO")
            session_code = create_session(token_env="GH_TOKEN_CODE")

            with ThreadPoolExecutor(max_workers=2) as pool:
                future_repo = pool.submit(
                    run_repo_search,
                    words_path=REPO_WORDS_PATH, output_dir=out,
                    session=session_repo, log=log,
                    delay=args.delay, limit=args.limit,
                )
                future_code = pool.submit(
                    run_code_search,
                    words_path=CODE_WORDS_PATH, output_dir=out,
                    session=session_code, log=log,
                    delay=args.delay, limit=args.limit,
                )

                for future in as_completed([future_repo, future_code]):
                    future.result()  # propagate exceptions
        else:
            # If `parallel_search` is not passed, run repo and code search sequentially.
            session = create_session()

            log.info("=== Stage 1: Repo search ===")
            run_repo_search(
                words_path=REPO_WORDS_PATH, output_dir=out,
                session=session, log=log,
                delay=args.delay, limit=args.limit,
            )

            log.info("=== Stage 2: Code search ===")
            run_code_search(
                words_path=CODE_WORDS_PATH, output_dir=out,
                session=session, log=log,
                delay=args.delay, limit=args.limit,
            )

    # Filter results
    if not args.skip_to_lang:
        log.info("=== Stage 3: Candidate filtering ===")
        run_candidate_filter(
            input_paths=[
                out / "repo_search_candidates.json",
                out / "code_search_candidates.json",
            ],
            output_path=out / "filtered_candidates.json",
            log=log,
        )

        # Collect PR comments from filtered repositories
        log.info("=== Stage 4: PR comment collection ===")
        session_pr = create_session()
        run_pr_collector(
            input_path=out / "filtered_candidates.json",
            output_path=out / "pr_comments.json",
            session=session_pr, log=log,
            limit=args.pr_limit,
        )

    # Filter out non-Romanian entries
    log.info("=== Stage 5: Language filtering ===")
    run_lang_filter(
        input_path=out / "pr_comments.json",
        output_dir=out,
        log=log,
    )

    # TODO: next steps

    log.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
