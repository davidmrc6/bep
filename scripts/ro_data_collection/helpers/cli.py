import argparse

from pathlib import Path
from constants.constants import WORDS_PATH, OUTPUT_DIR


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GitHub keyword search for Romanian repositories",
    )
    p.add_argument(
        "--words", type=Path, default=WORDS_PATH,
        help="Path to keywords file (default: full keyword list)",
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
        "--test", action="store_true",
        help="Use the small test keywords file instead of the full list",
    )
    return p.parse_args()
