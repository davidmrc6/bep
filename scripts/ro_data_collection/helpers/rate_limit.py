import time

from requests import Session
from logging import Logger
from constants.constants import RATE_LIMIT_URL

def check_rate_limit(session: Session) -> dict:
    """Returns the 'search' rate limit block from the GitHub API"""
    resp = session.get(RATE_LIMIT_URL)
    resp.raise_for_status()
    return resp.json()["resources"]["search"]

def wait_for_rate_limit(session: Session, log: Logger, buffer: int = 2):
    """Sleep until the search rate limit resets if remaining calls are low"""
    rl = check_rate_limit(session)
    remaining = rl["remaining"]
    reset_ts = rl["reset"]
    if remaining < buffer:
        wait = max(reset_ts - time.time(), 0) + 1
        log.warning(f"Rate limit nearly exhausted ({remaining} left). Sleeping {wait}s...")
        time.sleep(wait)
        log.info(f"Resumed after rate-limit wait.")
