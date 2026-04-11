"""
Manual review tool for Romanian comments.

Shows each comment one at a time with context. Press:
  y - accept (genuine Romanian code review)
  n - reject (translation, grammar fix, not code review, etc.)
  s - skip (come back to it later)
  q - quit and save progress
"""
import argparse
import json
from pathlib import Path

from constants.constants import OUTPUT_DIR

REVIEW_STATE_FILE = OUTPUT_DIR / "review_state.json"


def load_comments(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_state() -> dict:
    if REVIEW_STATE_FILE.exists():
        return json.loads(REVIEW_STATE_FILE.read_text(encoding="utf-8"))
    return {"decisions": {}}


def save_state(state: dict) -> None:
    REVIEW_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def comment_key(c: dict) -> str:
    """Unique key for a comment."""
    return f"{c.get('repo_full_name')}#{c.get('pr_number')}:{c.get('comment_type')}:{c.get('created_at')}:{c.get('author_login')}"


def main():
    p = argparse.ArgumentParser(description="Manually review Romanian comments")
    p.add_argument(
        "--input", type=Path, nargs="+",
        default=[
            OUTPUT_DIR / "ro_comments.json",
            OUTPUT_DIR / "ro_comments_review.json",
        ],
    )
    p.add_argument(
        "--output", type=Path,
        default=OUTPUT_DIR / "ro_comments_verified.json",
    )
    p.add_argument(
        "--review-only", action="store_true",
        help="Only show comments that haven't been reviewed yet",
    )
    args = p.parse_args()

    # Load all comments
    all_comments = []
    for path in args.input:
        if path.exists():
            all_comments.extend(load_comments(path))
    print(f"Loaded {len(all_comments)} comments from {len(args.input)} file(s)")

    state = load_state()
    decisions = state["decisions"]

    # Filter to unreviewed if requested
    to_review = []
    for c in all_comments:
        key = comment_key(c)
        if args.review_only and key in decisions:
            continue
        to_review.append(c)

    already_done = len(all_comments) - len(to_review)
    print(f"Already reviewed: {already_done}, remaining: {len(to_review)}")
    print(f"\nControls: [y]es  [n]o  [s]kip  [q]uit\n{'='*60}\n")

    for i, c in enumerate(to_review):
        key = comment_key(c)

        # Show existing decision if re-reviewing
        prev = decisions.get(key)
        prev_str = f" (previously: {prev})" if prev else ""

        conf = c.get("ro_confidence", "?")
        print(f"--- [{i+1}/{len(to_review)}] conf={conf}{prev_str} ---")
        print(f"Repo:   {c.get('repo_full_name')}")
        print(f"PR:     {c.get('pr_url')} ({c.get('comment_type')})")
        print(f"Author: {c.get('author_login')}")
        print(f"Title:  {c.get('pr_title')}")
        print()
        print(c.get("body", ""))
        print()

        while True:
            try:
                choice = input("[y/n/s/q] > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice in ("y", "n", "s", "q"):
                break
            print("Invalid input. Press y, n, s, or q.")

        if choice == "q":
            save_state(state)
            print(f"\nSaved. {sum(1 for v in decisions.values() if v == 'y')} accepted so far.")
            break
        elif choice in ("y", "n"):
            decisions[key] = choice
            save_state(state)
        # s = skip, don't record

    # Build final output
    accepted = []
    for c in all_comments:
        key = comment_key(c)
        if decisions.get(key) == "y":
            accepted.append(c)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(accepted, indent=2, ensure_ascii=False))

    total_y = sum(1 for v in decisions.values() if v == "y")
    total_n = sum(1 for v in decisions.values() if v == "n")
    total_pending = len(all_comments) - total_y - total_n
    print(f"\n{'='*60}")
    print(f"Accepted:  {total_y}")
    print(f"Rejected:  {total_n}")
    print(f"Pending:   {total_pending}")
    print(f"Written:   {args.output}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()⏎ 