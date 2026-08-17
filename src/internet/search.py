"""DuckDuckGo search with a short-lived TTL cache.

Same query within ``CACHE_TTL`` seconds returns instantly — the search
pipeline frequently re-issues similar or identical queries across the
score/rank/dedup cycle, so this avoids redundant network round-trips.
"""

from __future__ import annotations

import threading
import time

try:
    from ddgs import DDGS as SearchClient
except ImportError:  # pragma: no cover - fallback for older environments
    SearchClient = None

# How long (seconds) a cached search result stays valid.
CACHE_TTL = 120.0

# (query, max_results) -> (timestamp, results_list)
_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: tuple[str, int]) -> list[dict] | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        ts, results = entry
        if time.monotonic() - ts < CACHE_TTL:
            return results
        return None


def _cache_put(key: tuple[str, int], results: list[dict]) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic(), results)


def search(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo, returning a list of {title, url, snippet} dicts.

    Results are cached for ``CACHE_TTL`` seconds so repeated or near-duplicate
    queries in the same pipeline run pay zero network cost.
    """
    if SearchClient is None:
        return []

    cache_key = (query.strip().lower(), max_results)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        with SearchClient() as ddgs:
            results = ddgs.text(query, max_results=max_results)
    except Exception:
        return []

    parsed = [
        {
            "title": result.get("title", ""),
            "url": result.get("href", ""),
            "snippet": result.get("body", ""),
        }
        for result in results or []
    ]

    _cache_put(cache_key, parsed)
    return parsed