"""
Runs the full data collection pipeline.
"""
import argparse

from pathlib import Path

from constants.constants import (
    REPO_WORDS_PATH, CODE_WORDS_PATH, OUTPUT_DIR,
)
from helpers.log import setup_logging
from helpers.session import create_session

from repo_search import run_repo_search
from code_search import run_code_search
from candidate_filter import run_candidate_filter
from pr_collector import run_pr_collector
from issue_search import run_issue_search
from lang_filter import run_lang_filter
from helpers.aggregation import load_json, _save_json


def main():
    p = argparse.ArgumentParser(description="Run the full Romanian data collection pipeline")
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--delay", type=float, default=2.5)
    p.add_argument("--limit", type=int, default=None, help="Limit keywords per search stage")
    p.add_argument("--pr-limit", type=int, default=None, help="Limit repos for PR collection")
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

        log.info("=== Stage 3: Issue search ===")
        run_issue_search(
            words_path=CODE_WORDS_PATH, output_dir=out,
            session=session, log=log,
            delay=args.delay, limit=args.limit,
        )

    # Filter results
    if not args.skip_to_lang:
        log.info("=== Stage 4: Candidate filtering ===")
        run_candidate_filter(
            input_paths=[
                out / "repo_search_candidates.json",
                out / "code_search_candidates.json",
                out / "issue_search_candidates.json",
            ],
            output_path=out / "filtered_candidates.json",
            log=log,
        )

        # Collect PR comments from filtered repositories
        log.info("=== Stage 5: PR comment collection ===")
        session_pr = create_session()
        run_pr_collector(
            input_path=out / "filtered_candidates.json",
            output_path=out / "pr_comments.json",
            session=session_pr, log=log,
            limit=args.pr_limit,
        )

    # Filter out non-Romanian entries
    log.info("=== Stage 6: Language filtering ===")
    run_lang_filter(
        input_path=out / "pr_comments.json",
        output_dir=out,
        log=log,
    )

    # TODO: next steps

    log.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
