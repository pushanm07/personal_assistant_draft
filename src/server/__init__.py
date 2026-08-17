"""FastAPI HTTP layer for ALANA.

Exposes the assistant's "headless" departments (interpretation, chat,
composition, web answers, reminder parsing) as JSON endpoints so clients —
mobile apps, scripts, the CLI — can call them over HTTP without a browser or
GUI automation. GUI-bound actions (WhatsApp/Instagram sends, reminders that
click an iCloud page) are reported by ``/v1/route`` so a caller can decide how
to run them.

Run with::

    python -m src.server            # or: uvicorn src.server.app:app
"""

from __future__ import annotations

from .app import app, run

__all__ = ["app", "run"]
