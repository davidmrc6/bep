"""Run the full Romanian data collection pipeline."""
import argparse
from pathlib import Path

from constants.constants import REPO_WORDS_PATH, CODE_WORDS_PATH, OUTPUT_DIR
from helpers.log import setup_logging
from helpers.session import create_session

from repo_search import run_repo_search
from code_search import run_code_search
from issue_search import run_issue_search
from candidate_filter import run_candidate_filter
from pr_collector import run_pr_collector
from lang_filter import run_lang_filter
from post_filter import run_post_filter


def main():
    p = argparse.ArgumentParser(description="Run the Romanian data collection pipeline")
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--delay", type=float, default=2.5)
    p.add_argument("--limit", type=int, default=None, help="keywords per search stage")
    p.add_argument("--pr-limit", type=int, default=None, help="repos for PR collection")
    p.add_argument("--from", dest="start_from", default=None,
                   help="stage to start from (default: first)")
    p.add_argument("--to", dest="stop_at", default=None,
                   help="stage to stop at, inclusive (default: last)")
    args = p.parse_args()

    log = setup_logging()
    out = args.output_dir

    stages = [
        ("repo_search", lambda: run_repo_search(
            words_path=REPO_WORDS_PATH, output_dir=out,
            session=create_session(), log=log,
            delay=args.delay, limit=args.limit,
        )),
        ("code_search", lambda: run_code_search(
            words_path=CODE_WORDS_PATH, output_dir=out,
            session=create_session(), log=log,
            delay=args.delay, limit=args.limit,
        )),
        ("issue_search", lambda: run_issue_search(
            words_path=CODE_WORDS_PATH, output_dir=out,
            session=create_session(), log=log,
            delay=args.delay, limit=args.limit,
        )),
        ("candidate_filter", lambda: run_candidate_filter(
            input_paths=[
                out / "repo_search_candidates.json",
                out / "code_search_candidates.json",
                out / "issue_search_candidates.json",
            ],
            output_path=out / "filtered_candidates.json",
            log=log,
        )),
        ("pr_collector", lambda: run_pr_collector(
            input_path=out / "filtered_candidates.json",
            output_path=out / "pr_comments.json",
            session=create_session(), log=log,
            limit=args.pr_limit,
        )),
        ("lang_filter", lambda: run_lang_filter(
            input_path=out / "pr_comments.json",
            output_dir=out, log=log,
        )),
        ("post_filter", lambda: run_post_filter(
            input_path=out / "ro_comments_review.json",
            clean_path=out / "ro_comments_clean.json",
            rejected_path=out / "ro_comments_rejected.json",
            log=log,
        )),
    ]

    names = [n for n, _ in stages]
    if args.start_from and args.start_from not in names:
        p.error(f"--from must be one of: {', '.join(names)}")
    if args.stop_at and args.stop_at not in names:
        p.error(f"--to must be one of: {', '.join(names)}")

    start = names.index(args.start_from) if args.start_from else 0
    stop = names.index(args.stop_at) if args.stop_at else len(stages) - 1
    if start > stop:
        p.error("--from must precede --to")

    for name, runner in stages[start:stop + 1]:
        log.info("STAGE      [pipeline] %s", name)
        runner()
    log.info("DONE       [pipeline] all stages complete")


if __name__ == "__main__":
    """
    Usage:
    ```
    python pipeline.py --from <FROM_STAGE> --to <TO_STAGE>
    ```
    """
    main()
