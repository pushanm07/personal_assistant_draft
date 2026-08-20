"""News actions for ALANA."""

from __future__ import annotations

from brain import llm
from services.news import build_context, fetch_news


def get_news(topic: str | None = None) -> str:
    """Return a concise, factual summary of current news."""
    articles = fetch_news(topic)
    if not articles:
        return "I couldn't find any current news for that request, Sir."

    context = build_context(articles)
    if not llm.available:
        return "\n".join(
            f"{index}. {article['title']} ({article['source']})"
            for index, article in enumerate(articles, start=1)
        )

    summary = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "Summarize only the supplied current-news context. Do not add "
                    "facts, speculation, or details not present. Be concise, factual, "
                    "and mention sources when useful."
                ),
            },
            {"role": "user", "content": context},
        ],
        temperature=0.1,
        num_predict=llm.MAX_ANSWER_TOKENS,
    )
    return (summary or "").strip() or context
