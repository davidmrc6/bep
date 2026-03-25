"""
Preflight check for the ro_data_collection pipeline.
Verifies dependencies, environment, folders, and API access before running.

Usage:
    python preflight.py [--skip-api]
"""

import os
import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
warned = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg):
    global warned
    warned += 1
    print(f"  {YELLOW}⚠{RESET} {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


# Check python dependencies
def check_dependencies():
    print(f"\n{BOLD}[1/5] Python packages{RESET}")
    required = {
        "requests": "requests",
        "dotenv": "python-dotenv",
        "lingua": "lingua-language-detector",
    }
    for import_name, pip_name in required.items():
        try:
            __import__(import_name)
            ok(f"{pip_name}")
        except ImportError:
            fail(f"{pip_name} not installed  →  pip install {pip_name}")


# Check env and tokens
def check_env():
    print(f"\n{BOLD}[2/5] Environment (.env){RESET}")
    import os

    env_path = SCRIPT_DIR / ".env"
    if not env_path.exists():
        fail(f".env file not found at {env_path}")
        return {}

    ok(".env file exists")

    # load it so we can inspect values
    from dotenv import load_dotenv

    load_dotenv(env_path, override=False)

    tokens = {}
    for var in ("GH_TOKEN", "GH_TOKEN_REPO", "GH_TOKEN_CODE"):
        val = os.getenv(var)
        if val:
            ok(f"{var} is set")
            tokens[var] = val
        elif var == "GH_TOKEN":
            fail(f"{var} is missing — required for all API calls")
        else:
            warn(f"{var} is not set (only needed for --parallel-search)")

    return tokens


# Check dictionaries
def check_dictionaries():
    print(f"\n{BOLD}[3/5] Keyword dictionaries{RESET}")
    for name in ("keywords_repo.txt", "keywords_code.txt"):
        p = SCRIPT_DIR / "__dictionaries__" / name
        if not p.exists():
            fail(f"{p.relative_to(SCRIPT_DIR)} not found")
        elif p.stat().st_size == 0:
            warn(f"{p.relative_to(SCRIPT_DIR)} exists but is empty")
        else:
            lines = [l for l in p.read_text().splitlines() if l.strip()]
            ok(f"{p.relative_to(SCRIPT_DIR)}  ({len(lines)} keywords)")


# Check directories
def check_directories():
    print(f"\n{BOLD}[4/5] Output / cache directories{RESET}")
    for name in ("__cache__", "__output__", "__logs__"):
        p = SCRIPT_DIR / name
        if p.exists():
            if os.access(p, os.W_OK):
                ok(f"{name}/ exists and is writable")
            else:
                fail(f"{name}/ exists but is NOT writable")
        else:
            # pipeline creates these automatically, just note it
            warn(f"{name}/ does not exist yet (will be created on first run)")


# Check GitHub connectivity
def check_api(tokens):
    print(f"\n{BOLD}[5/5] GitHub API connectivity{RESET}")
    if not tokens.get("GH_TOKEN"):
        warn("skipped — no GH_TOKEN available")
        return

    import requests

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {tokens['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
        }
    )

    # basic auth check
    try:
        r = session.get("https://api.github.com/user", timeout=10)
        if r.status_code == 200:
            ok(f"authenticated as {r.json().get('login', '?')}")
        elif r.status_code == 401:
            fail("GH_TOKEN is invalid or expired (401)")
            return
        else:
            fail(f"unexpected status {r.status_code} from /user")
            return
    except requests.ConnectionError:
        fail("cannot reach api.github.com — check your network")
        return
    except requests.Timeout:
        fail("request to api.github.com timed out")
        return

    # search rate limit
    try:
        r = session.get("https://api.github.com/rate_limit", timeout=10)
        if r.status_code == 200:
            search = r.json().get("resources", {}).get("search", {})
            remaining = search.get("remaining", "?")
            limit = search.get("limit", "?")
            if isinstance(remaining, int) and remaining == 0:
                warn(f"search rate limit exhausted ({remaining}/{limit})")
            else:
                ok(f"search rate limit: {remaining}/{limit} remaining")
    except Exception:
        warn("could not check rate limit")


def main():
    parser = argparse.ArgumentParser(description="Pipeline preflight checks")
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="skip the GitHub API connectivity check",
    )
    args = parser.parse_args()

    print(f"{BOLD}ro_data_collection — preflight check{RESET}")

    check_dependencies()
    tokens = check_env()
    check_dictionaries()

    check_directories()

    if args.skip_api:
        print(f"\n{BOLD}[5/5] GitHub API connectivity{RESET}")
        warn("skipped (--skip-api)")
    else:
        check_api(tokens)

    # summary
    print(f"\n{'─' * 40}")
    parts = [f"{GREEN}{passed} passed{RESET}"]
    if warned:
        parts.append(f"{YELLOW}{warned} warnings{RESET}")
    if failed:
        parts.append(f"{RED}{failed} failed{RESET}")
    print(f"  {', '.join(parts)}")

    if failed:
        print(f"\n  Fix the issues above before running the pipeline.\n")
        sys.exit(1)
    else:
        print(f"\n  {GREEN}Ready to go!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
