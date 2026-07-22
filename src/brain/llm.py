"""Shared Ollama client for ALANA.

Every component that talks to the local model goes through here so they all
get the same latency tuning in one place:

- ``keep_alive`` keeps the model resident in memory between calls, which
  removes the multi-second cold-start reload that otherwise hits the first
  request after any idle gap. This is the single biggest latency win.
- ``num_predict`` caps how many tokens the model may generate, so short
  answers come back quickly instead of the model rambling.
- ``warm_up`` primes the model at startup (in a background thread) so the
  first real command is already fast.
"""

from __future__ import annotations

import threading
from typing import Any

try:
    from ollama import chat as _ollama_chat
except ImportError:  # pragma: no cover - optional dependency
    _ollama_chat = None


DEFAULT_MODEL = "llama3.2:latest"

# Keep the model loaded between requests so we never pay the reload cost.
KEEP_ALIVE = "30m"

# True when a local Ollama runtime is importable.
available = _ollama_chat is not None


def chat(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    fmt: str | None = None,
    num_predict: int = 256,
    temperature: float = 0.4,
    top_k: int = 40,
) -> str | None:
    """Call Ollama and return the assistant's text.

    Returns ``None`` when Ollama is unavailable or the call fails, so callers
    can cleanly fall back to their offline behaviour.
    """
    if _ollama_chat is None:
        return None

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "top_k": top_k,
        },
    }
    if fmt:
        kwargs["format"] = fmt

    try:
        response = _ollama_chat(**kwargs)
        content = response["message"]["content"]
        return content if isinstance(content, str) else None
    except Exception:  # pragma: no cover - model/runtime failures
        return None


def warm_up(model: str = DEFAULT_MODEL) -> None:
    """Load the model into memory so the first real request is fast."""
    if _ollama_chat is None:
        return
    try:
        _ollama_chat(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            keep_alive=KEEP_ALIVE,
            options={"num_predict": 1},
        )
    except Exception:  # pragma: no cover - best effort
        pass


def warm_up_async(model: str = DEFAULT_MODEL) -> None:
    """Kick off :func:`warm_up` in a daemon thread without blocking startup."""
    threading.Thread(target=warm_up, args=(model,), daemon=True).start()
