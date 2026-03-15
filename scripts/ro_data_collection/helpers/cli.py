import argparse

from pathlib import Path
from constants.constants import REPO_WORDS_PATH, CODE_WORDS_PATH, OUTPUT_DIR


def parse_repo_search_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GitHub repository keyword search for Romanian repos",
    )
    p.add_argument(
        "--words", type=Path, default=REPO_WORDS_PATH,
        help="Path to keywords file (default: repo keyword list)",
    )
    p.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR,
        help="Directory to write result JSON files",
    )
    p.add_argument(
        "--delay", type=float, default=2.5,
        help="Seconds to wait between queries (default: 2.5)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Only use the first N keywords from the dictionary",
    )
    return p.parse_args()


def parse_code_search_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GitHub code keyword search for Romanian repos",
    )
    p.add_argument(
        "--words", type=Path, default=CODE_WORDS_PATH,
        help="Path to keywords file (default: code keyword list)",
    )
    p.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR,
        help="Directory to write result JSON files",
    )
    p.add_argument(
        "--delay", type=float, default=2.5,
        help="Seconds to wait between queries (default: 2.5)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Only use the first N keywords from the dictionary",
    )
    return p.parse_args()
