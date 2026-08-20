"""Small, cleaned client for The News API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILES = (PROJECT_ROOT / "config" / "key.txt", PROJECT_ROOT / "config" / "keys.txt")
NEWS_ENDPOINT = "https://api.thenewsapi.com/v1/news/all"


def _load_token() -> str:
    for path in TOKEN_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                name, value = stripped.split("=", 1)
                if name.strip() == "THE_NEWS_API_TOKEN" and value.strip():
                    return value.strip()
            elif path.name == "key.txt" and stripped:
                return stripped
    raise RuntimeError("The News API token was not found in config/key.txt or config/keys.txt.")


def fetch_news(topic: str | None = None, limit: int = 5) -> list[dict[str, str]]:
    """Fetch a small set of current articles and return cleaned fields only."""
    params: dict[str, Any] = {
        "api_token": _load_token(),
        "language": "en",
        "limit": max(1, min(limit, 5)),
        "sort": "published_at",
    }
    if topic and topic.strip():
        params["search"] = topic.strip()

    response = requests.get(NEWS_ENDPOINT, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    articles: list[dict[str, str]] = []
    for item in payload.get("data", []):
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        description = re.sub(r"\s+", " ", str(item.get("description") or "")).strip()
        if not title:
            continue
        articles.append(
            {
                "title": title[:240],
                "description": description[:500],
                "source": str(item.get("source") or "unknown").strip()[:120],
                "published_at": str(item.get("published_at") or "").strip()[:40],
                "url": str(item.get("url") or "").strip()[:300],
            }
        )
    return articles


def build_context(articles: list[dict[str, str]]) -> str:
    """Format only concise article facts for the summarizer."""
    return "\n".join(
        f"- {article['title']} | {article['source']} | {article['published_at']}\n"
        f"  {article['description']}"
        for article in articles
    )
