"""Decide whether a question needs a live web search.

This used to round-trip the LLM to answer "YES or NO", adding hundreds of
milliseconds to every answer before any search even started. It now uses a
fast, deterministic heuristic: personal/device/local commands obviously don't
need the web, while everything else factual/current does. No model call, no
latency.

``src/actions/web.py`` drives its own search pipeline and does not import this;
the function is kept as a lightweight guard for anything that wants a quick
"search or not" decision.
"""

from __future__ import annotations

import re

# Phrases that relate to the user's own machine/accounts and never need a web
# search to resolve.
_LOCAL_HINTS = (
    "my ",
    "my spotify",
    "my whatsapp",
    "my instagram",
    "my phone",
    "my computer",
    "my laptop",
    "my device",
    "version",
    "installed",
    "update my",
    "open ",
    "close ",
    "play ",
    "pause",
    "resume",
)

_INTERROGATIVES = r"\b(what|who|where|when|why|how|is|are|does|do|can|will)\b"


def should_search(question: str) -> bool:
    """Return True when *question* is best answered from the live web."""
    text = re.sub(r"\s+", " ", (question or "").lower()).strip()
    if not text:
        return False

    # Clear local/device commands never need the web.
    if any(hint in text for hint in _LOCAL_HINTS):
        return False

    # Information-gathering phrasing generally benefits from a search unless it
    # was caught above as local.
    return bool(re.search(_INTERROGATIVES, text))

