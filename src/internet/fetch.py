"""Connection-reusing, cached HTTP downloads for ALANA's web department.

Latency notes
-------------
- A single ``requests.Session`` is reused for every download instead of
  opening a fresh connection each time. Keep-alive means subsequent page
  fetches reuse the same TCP/TLS connections instead of paying a full
  handshake for every URL, which is the dominant cost when scraping several
  pages in a row.
- A small thread-safe TTL cache returns pages that were fetched moments ago
  instantly. The search pipeline frequently re-encounters the same URL across
  query variants, so this avoids re-downloading redundant pages.
- Transient network failures are retried with light backoff, so one flaky
  request does not force the whole pipeline to run with an empty context.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

DEFAULT_TIMEOUT = 10.0

# How many times to retry a page after a transient failure.
MAX_RETRIES = 2

# Successful/failed downloads are kept this long so repeated fetches of the
# same URL in a short window short-circuit without any network I/O.
CACHE_TTL = 30.0

# Reuse up to this many connections per host instead of one at a time.
POOL_CONNECTIONS = 10
POOL_MAXSIZE = 10

_session: requests.Session | None = None
_session_lock = threading.Lock()

_cache: dict[str, tuple[float, str | None]] = {}
_cache_lock = threading.Lock()


def _get_session() -> requests.Session:
    """Return the process-wide keep-alive session, building it once."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                session = requests.Session()
                session.headers.update(HEADERS)
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=POOL_CONNECTIONS,
                    pool_maxsize=POOL_MAXSIZE,
                    max_retries=0,  # retries handled below with backoff
                )
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                _session = session
    return _session


def _download_once(url: str, timeout: float) -> str | None:
    """Perform a single download with no retry or caching."""
    try:
        response = _get_session().get(url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def _cache_get(url: str) -> tuple[float, str | None] | None:
    with _cache_lock:
        entry = _cache.get(url)
        if entry is None:
            return None
        return entry[0], entry[1]


def _cache_put(url: str, text: str | None) -> None:
    with _cache_lock:
        _cache[url] = (time.monotonic(), text)


def download(url: Any, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Download one webpage, reusing keep-alive connections and a TTL cache.

    Returns the page HTML, or ``None`` on failure. Concurrent calls are safe.
    """
    url = str(url)
    now = time.monotonic()

    cached = _cache_get(url)
    if cached is not None and now - cached[0] < CACHE_TTL:
        return cached[1]

    text: str | None = None
    for attempt in range(MAX_RETRIES + 1):
        text = _download_once(url, timeout)
        if text is not None:
            break
        if attempt < MAX_RETRIES:
            time.sleep(0.25 * (attempt + 1))

    _cache_put(url, text)
    return text