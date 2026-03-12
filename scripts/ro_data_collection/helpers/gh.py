import math
import time

from pathlib import Path
from requests import Session, Response, HTTPError
from logging import Logger
from datetime import datetime, timezone
from helpers.rate_limit import wait_for_rate_limit
from helpers.caching import _cache_key, load_meta, load_page, save_meta, save_page

PER_PAGE = 100
MAX_RESULTS = 1000
MAX_PAGES = MAX_RESULTS // PER_PAGE

def _do_search_request(url: str, params: dict, session: Session, log: Logger) -> Response:
    """Execute single search request"""
    wait_for_rate_limit(session, log, buffer=2)
    resp = session.get(url, params=params)

    # Handle secondary rate limits (HTTP 403 with Retry-After res header)
    # If Retry-After header not present, default to 60s
    if resp.status_code == 403:
        retry_after = int(resp.headers.get("Retry-After", 60))
        log.warning(f"403 Rate Limit. Sleeping {retry_after}s...")
        time.sleep(retry_after)
        resp = session.get(url, params = params)            # TODO: what if this also throws a 403?

    # Handle server errors with single retry
    if resp.status_code in (500, 502, 503):
        log.warning(f"Server error {resp.status_code}. Retrying in 10 seconds...")
        time.sleep(10)
        resp = session.get(url, params = params)

    resp.raise_for_status()
    return resp

def search_paginated(
        query: str,
        search_url: str,
        cache_dir: Path,
        session: Session,
        log: Logger,
        extra_params: dict | None = None,
) -> list[dict]:
    """
    Paginate through a GitHub search endpoint for `query`.
    Returns the list of items across all pages (up to 1000). TODO: extend if possible?
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
        return items

    # After checking cache, determine start page
    start_page = 1
    if meta and meta.get("status" == "partial"):
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
        except HTTPError as exc:
            log.error("HTTP error for q='%s' page=%d: %s", query, page, exc)
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
            return all_items

        data = resp.json()
        save_page(cache_dir, key, page, data)
        pages_fetched = page

        if total_count is None:
            total_count = data.get("total_count", 0)
            log.info("           total_count=%d for q='%s'", total_count, query)

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
        log.warning("OVERFLOW   q='%s' has %d results (capped at %d).", query, total_count, MAX_RESULTS)

    log.info("DONE       [%s] q='%s' → %d items fetched", cache_dir.name, query, len(all_items))
    return all_items