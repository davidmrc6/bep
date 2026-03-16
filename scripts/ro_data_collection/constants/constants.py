from pathlib import Path

REPO_WORDS_PATH = Path("./__dictionaries__/keywords_repo.txt")
CODE_WORDS_PATH = Path("./__dictionaries__/keywords_code.txt")
TEST_WORDS_PATH = Path("./__dictionaries__/keywords_test.txt")

CACHE_DIR = Path("./__cache__")
REPO_CACHE_DIR = CACHE_DIR / "repo_search"
CODE_CACHE_DIR = CACHE_DIR / "code_search"
PR_CACHE_DIR = CACHE_DIR / "pr_collection"

SEARCH_REPOS_URL = "https://api.github.com/search/repositories"
SEARCH_CODE_URL = "https://api.github.com/search/code"
RATE_LIMIT_URL = "https://api.github.com/rate_limit"

OUTPUT_DIR = Path("./__output__")
LOG_DIR = Path("./__logs__")
