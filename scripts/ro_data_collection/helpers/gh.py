import json
import math
import re
import time

from pathlib import Path
from requests import Session, Response, HTTPError, RequestException, ConnectionError as ReqConnectionError
from logging import Logger
from datetime import datetime, timezone
from helpers.rate_limit import wait_for_rate_limit
from helpers.caching import _cache_key, load_meta, load_page, save_meta, save_page
from constants.constants import META_CACHE_DIR

PER_PAGE = 100
MAX_RESULTS = 1000
MAX_PAGES = MAX_RESULTS // PER_PAGE
MAX_RETRIES = 3
RETRY_BACKOFF = [10, 30, 60]  # seconds to wait per retry attempt


def _wait_and_retry(resp: Response, url: str, params: dict, session: Session, log: Logger) -> Response:
    """Handle rate limits (403/429) and server errors (5xx) with a single retry."""
    if resp.status_code in (403, 429):
        # Retry-After header (seconds), or fall back to x-ratelimit-reset (unix ts)
        retry_after = resp.headers.get("Retry-After")
        try:
            if retry_after is not None:
                wait = int(retry_after)
            else:
                reset_ts = resp.headers.get("x-ratelimit-reset")
                if reset_ts is not None:
                    wait = max(int(reset_ts) - int(time.time()), 0) + 1
                else:
                    wait = 60
        except (ValueError, TypeError):
            wait = 60
        log.warning("RATE LIMIT [http] %d on %s — sleeping %ds", resp.status_code, url, wait)
        time.sleep(wait)
        resp = session.get(url, params=params)

    if resp.status_code in (500, 502, 503):
        log.warning("RETRY      [http] server error %d on %s — retrying in 10s", resp.status_code, url)
        time.sleep(10)
        resp = session.get(url, params=params)

    return resp


def _request_with_retries(url: str, params: dict, session: Session, log: Logger) -> Response:
    """Execute a request with retries on connection errors (RemoteDisconnected, resets, etc)."""
    for attempt in range(MAX_RETRIES):
        try:
            return session.get(url, params=params)
        except (ReqConnectionError, ConnectionError) as exc:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            log.warning("CONNRESET  [http] %s on attempt %d/%d — retrying in %ds: %s",
                        url, attempt + 1, MAX_RETRIES, wait, exc)
            time.sleep(wait)
    # final attempt — let it raise if it fails
    return session.get(url, params=params)


def _do_search_request(url: str, params: dict, session: Session, log: Logger) -> Response:
    """Execute single search request (uses search rate limit)."""
    wait_for_rate_limit(session, log, buffer=2)
    resp = _request_with_retries(url, params, session, log)
    resp = _wait_and_retry(resp, url, params, session, log)
    resp.raise_for_status()
    return resp


def _do_core_request(url: str, params: dict, session: Session, log: Logger) -> Response:
    """Execute a core API request with rate limit and error handling."""
    resp = _request_with_retries(url, params, session, log)
    resp = _wait_and_retry(resp, url, params, session, log)
    return resp

def search_paginated(
        query: str,
        search_url: str,
        cache_dir: Path,
        session: Session,
        log: Logger,
        extra_params: dict | None = None,
) -> tuple[list[dict], bool]:
    """
    Paginate through a GitHub search endpoint for `query`.
    Returns (items, cached) — the list of items across all pages (up to 1000),
    and a bool indicating whether the result came entirely from cache.
    Raw JSON pages are cached, so completed queries are skipped on re-runs.
    """
    key = _cache_key(query)
    meta = load_meta(cache_dir, key)

    # Check cache
    if meta and meta.get("status") == "complete":
        log.info("CACHE HIT  [%s] q='%s' (%d items)", cache_dir.name, query, meta["total_items"])
        items = []
        for p in range(1, meta["pages_fetched"] + 1):
            page_data = load_page(cache_dir, key, p)
            if page_data:
                items.extend(page_data.get("items", []))
        return items, True

    # After checking cache, determine start page
    start_page = 1
    if meta and meta.get("status") == "partial":
        start_page = meta.get("pages_fetched", 0) + 1
        log.info("RESUME     [%s] q='%s' from page %d", cache_dir.name, query, start_page)


    params = {"q": query, "per_page": PER_PAGE, **(extra_params or {})}

    all_items: list[dict] = []

    # Load cached pages
    for p in range(1, start_page):
        page_data = load_page(cache_dir, key, p)
        if page_data:
            all_items.extend(page_data.get("items", []))

    total_count = None
    pages_fetched = start_page - 1

    # Fetch remaining pages
    for page in range(start_page, MAX_PAGES + 1):
        params["page"] = page
        log.info("FETCH      [%s] q='%s' page=%d", cache_dir.name, query, page)

        try:
            resp = _do_search_request(search_url, params, session, log)
            data = resp.json()
        except (HTTPError, RequestException, ValueError) as exc:
            log.error("ERROR      [%s] q='%s' page=%d: %s", cache_dir.name, query, page, exc)
            # Save partial progress
            save_meta(cache_dir, key, {
                "query": query,
                "status": "partial",
                "pages_fetched": pages_fetched,
                "total_count": total_count,
                "total_items": len(all_items),
                "error": str(exc),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            return all_items, False
        save_page(cache_dir, key, page, data)
        pages_fetched = page

        if total_count is None:
            total_count = data.get("total_count", 0)
            log.info("INFO       [%s] total_count=%d for q='%s'", cache_dir.name, total_count, query)

        page_items = data.get("items", [])
        all_items.extend(page_items)

        # Stop early if we've got everything
        total_pages_needed = min(math.ceil(total_count / PER_PAGE), MAX_PAGES)
        if page >= total_pages_needed or len(page_items) < PER_PAGE:
            break

        # Small courtesy delay between pages to stay under 30 req/min GH limit
        time.sleep(2.5)

    # Mark search as complete
    overflow = (total_count or 0) > MAX_RESULTS
    save_meta(cache_dir, key, {
        "query": query,
        "status": "complete",
        "pages_fetched": pages_fetched,
        "total_count": total_count,
        "total_items": len(all_items),
        "overflow": overflow,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # TODO: find way to handle overflow
    if overflow:
        log.warning("OVERFLOW   [%s] q='%s' has %d results (capped at %d)", cache_dir.name, query, total_count, MAX_RESULTS)

    log.info("DONE       [%s] q='%s' → %d items fetched", cache_dir.name, query, len(all_items))
    return all_items, False


def paginate_core(
    url: str, session: Session, log: Logger,
    params: dict | None = None,
    per_page: int = 100,
    max_pages: int = 100,
) -> list[dict]:
    """
    Generic paginated fetch for core API list endpoints.
    Returns all items across pages. Stops when a page has fewer than per_page items
    or max_pages is reached.
    """
    params = {**(params or {}), "per_page": per_page}
    all_items: list[dict] = []

    for page in range(1, max_pages + 1):
        params["page"] = page
        resp = _do_core_request(url, params, session, log)

        if not resp.ok:
            log.warning("WARN       [core_api] %s page=%d returned %d", url, page, resp.status_code)
            break

        if resp.status_code == 204 or not resp.text.strip():
            break

        try:
            items = resp.json()
        except ValueError:
            log.warning("WARN       [core_api] %s page=%d returned non-JSON", url, page)
            break
        if not isinstance(items, list):
            break

        all_items.extend(items)
        if len(items) < per_page:
            break

    return all_items


def fetch_repo_info(full_name: str, session: Session, log: Logger) -> dict | None:
    """
    Fetch full repository metadata via GET /repos/{owner}/{repo}.
    Uses core rate limit. Returns the raw JSON dict, or None on failure.
    """
    url = f"https://api.github.com/repos/{full_name}"
    resp = _do_core_request(url, {}, session, log)

    if resp.status_code == 404:
        log.warning("WARN       [repo_meta] repo info %s not found (404)", full_name)
        return None
    if not resp.ok:
        log.warning("WARN       [repo_meta] repo info %s returned %d", full_name, resp.status_code)
        return None

    return resp.json()


def fetch_total_pr_count(full_name: str, session: Session, log: Logger) -> int | None:
    """
    Fetch the total number of PRs (open + closed) for a repo.
    Uses GET /repos/{owner}/{repo}/pulls?state=all&per_page=1 and parses the
    Link header to extract the last page number, which equals the total count.
    Uses core rate limit (5000/hr), not search rate limit.
    Returns None on failure.
    """
    url = f"https://api.github.com/repos/{full_name}/pulls"
    params = {"state": "all", "per_page": 1}
    resp = _do_core_request(url, params, session, log)

    if resp.status_code == 404:
        log.warning("WARN       [repo_meta] PR count %s not found (404)", full_name)
        return None
    if not resp.ok:
        log.warning("WARN       [repo_meta] PR count %s returned %d", full_name, resp.status_code)
        return None

    link = resp.headers.get("Link", "")
    # Link header: <...?page=42>; rel="last"
    match = re.search(r'[&?]page=(\d+)>;\s*rel="last"', link)
    if match:
        return int(match.group(1))

    # No Link header means 0 or 1 PRs, so check body
    body = resp.json()
    return len(body)


def fetch_contributor_info(
    full_name: str, session: Session, log: Logger,
) -> dict:
    """
    Fetch contributor count and human contributor count for a repo.
    Uses GET /repos/{owner}/{repo}/contributors?per_page=100&anon=false.
    One API call (core rate limit). Returns:
        {"total_contributors": int|None, "human_contributors": int|None}
    For repos with <=100 contributors, human_contributors is exact.
    For repos with >100, it's a lower bound (first 100 only).
    """
    url = f"https://api.github.com/repos/{full_name}/contributors"
    params = {"per_page": 100, "anon": "false"}
    resp = _do_core_request(url, params, session, log)

    if resp.status_code == 404:
        log.warning("WARN       [repo_meta] contributors %s not found (404)", full_name)
        return {"total_contributors": None, "human_contributors": None}
    if not resp.ok:
        log.warning("WARN       [repo_meta] contributors %s returned %d", full_name, resp.status_code)
        return {"total_contributors": None, "human_contributors": None}

    # 204 No Content = empty repo, or non-JSON response
    if resp.status_code == 204 or not resp.text.strip():
        return {"total_contributors": 0, "human_contributors": 0}

    body = resp.json()
    if not isinstance(body, list):
        return {"total_contributors": 0, "human_contributors": 0}

    # Total count from Link header
    link = resp.headers.get("Link", "")
    match = re.search(r'[&?]page=(\d+)>;\s*rel="last"', link)
    if match:
        total = int(match.group(1)) * 100  # upper bound estimate
        # Fetch exact count from last page would cost another call, so estimate
        # For our filtering purposes this is fine
    else:
        total = len(body)

    human_count = sum(1 for c in body if _is_human(c))

    return {"total_contributors": total, "human_contributors": human_count}


# Common bot account name patterns (lowercase)
_BOT_NAME_PATTERNS = re.compile(
    r"(^|\W)(bot|ci|automation)(\W|$)"
    r"|dependabot|renovate|greenkeeper|snyk-bot|imgbot|codecov"
    r"|github-actions|mergify|semantic-release|release-please"
    r"|copilot|claude|openai|devin|cursor|coderabbit|sourcery"
    r"|\[bot]$",
    re.IGNORECASE,
)


def _is_human(contributor: dict) -> bool:
    """Check if a contributor is likely a human (not a bot or app)."""
    if contributor.get("type") == "Bot":
        return False
    login = (contributor.get("login") or "").lower()
    if _BOT_NAME_PATTERNS.search(login):
        return False
    return True


def _meta_cache_path(full_name: str) -> Path:
    slug = full_name.replace("/", "__")
    return META_CACHE_DIR / f"{slug}.json"


def fetch_repo_meta_cached(
    full_name: str, session: Session, log: Logger,
    progress: tuple[int, int] | None = None,
) -> dict:
    """
    Fetch repo info + PR count + contributor info, with file-based caching.
    Returns dict with keys: total_pr_count, total_contributors, human_contributors,
    and optionally repo_info (full repo API response) for code_search usage.
    progress: optional (current, total) tuple for log messages.
    """
    prog = f" {progress[0]}/{progress[1]}" if progress else ""
    cache_path = _meta_cache_path(full_name)
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            log.info("CACHE HIT  [repo_meta%s] %s", prog, full_name)
            return cached
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("CORRUPT    [repo_meta%s] %s — re-fetching", prog, full_name)

    log.info("FETCH      [repo_meta%s] %s (repo info + PRs + contributors)", prog, full_name)
    repo_info = fetch_repo_info(full_name, session, log)
    pr_count = fetch_total_pr_count(full_name, session, log)
    contrib_info = fetch_contributor_info(full_name, session, log)
    meta = {
        "repo_info": repo_info,
        "total_pr_count": pr_count,
        **contrib_info,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(meta, ensure_ascii=False))
    return meta