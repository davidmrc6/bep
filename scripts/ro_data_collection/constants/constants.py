from pathlib import Path

WORDS_PATH = Path("./__dictionaries__/keywords.txt")
TEST_WORDS_PATH = Path("./__dictionaries__/keywords_test.txt")

CACHE_DIR = Path("./__cache__")
REPO_CACHE_DIR = CACHE_DIR / "repo_search"
CODE_CACHE_DIR = CACHE_DIR / "code_search"

SEARCH_REPOS_URL = "https://api.github.com/search/repositories"
SEARCH_CODE_URL = "https://api.github.com/search/code"
RATE_LIMIT_URL = "https://api.github.com/rate_limit"

OUTPUT_DIR = Path("./__output__")
LOG_DIR = Path("./__logs__")
