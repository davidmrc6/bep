import time

from requests import Session
from logging import Logger
from constants.constants import RATE_LIMIT_URL

def check_rate_limit(session: Session) -> dict | None:
    """Returns the 'search' rate limit block from the GitHub API, or None on failure."""
    try:
        resp = session.get(RATE_LIMIT_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()["resources"]["search"]
    except Exception:
        return None

def wait_for_rate_limit(session: Session, log: Logger, buffer: int = 2):
    """Sleep until the search rate limit resets if remaining calls are low."""
    rl = check_rate_limit(session)
    if rl is None:
        # Can't check rate limit, so wait a bit as a precaution and continue
        log.warning("Could not check rate limit. Sleeping 5s as precaution...")
        time.sleep(5)
        return
    remaining = rl["remaining"]
    reset_ts = rl["reset"]
    if remaining < buffer:
        wait = max(reset_ts - time.time(), 0) + 1
        log.warning("Rate limit nearly exhausted (%d left). Sleeping %ds...", remaining, wait)
        time.sleep(wait)
        log.info("Resumed after rate-limit wait.")
