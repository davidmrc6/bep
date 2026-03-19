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
        log.warning("WARN       [rate_limit] could not check — sleeping 5s as precaution")
        time.sleep(5)
        return
    remaining = rl["remaining"]
    reset_ts = rl["reset"]
    if remaining < buffer:
        wait = max(reset_ts - time.time(), 0) + 1
        log.warning("WAIT       [rate_limit] %d remaining — sleeping %ds until reset", remaining, wait)
        time.sleep(wait)
        log.info("RESUME     [rate_limit] resumed after wait")
