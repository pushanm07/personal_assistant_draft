"""FastAPI application exposing ALANA's headless departments over HTTP.

Endpoints (all JSON):

- ``GET  /v1/health``           system + model status
- ``GET  /v1/contacts``         known messaging contacts
- ``GET  /v1/actions``          configured action list
- ``POST /v1/interpret``        structured intent from raw text
- ``POST /v1/chat``             conversational reply (no action executed)
- ``POST /v1/compose``          draft a message from a recipient + intent
- ``POST /v1/answer``           answer a question from the web
- ``POST /v1/reminder/parse``   parse a reminder phrase into text/dt/frequency
- ``POST /v1/route``            interpret + tell the caller how to run it

Sync endpoints are declared as ordinary ``def`` so FastAPI runs them in its
thread pool — blocking work (Ollama calls, web fetches) never blocks other
requests.

Entry points: ``python -m src.server`` or ``uvicorn src.server.app:app``.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Make flat modules (actions.*, brain.*, internet.*) importable no matter how
# this module is launched.
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from actions.reminder import parse_reminder_request  # noqa: E402
from actions.web import get_answer  # noqa: E402
from brain import llm  # noqa: E402
from brain.brain import Brain  # noqa: E402
from brain.composer import Composer  # noqa: E402
from brain.interpreter import Interpreter  # noqa: E402

# Actions that can be completed from the API without desktop/browser automation.
HEADLESS_ACTIONS = {"answer_question", "get_news", "read_email", "check_calendar"}

# Actions that talk to the Spotify Web API (need an authenticated token).
SPOTIFY_ACTIONS = {
    "play_song",
    "pause_song",
    "resume_song",
    "previous_song",
    "next_song",
}

# Module-level singletons so config files / models are only ever loaded once.
BRAIN = Brain()
INTERPRETER: Interpreter = BRAIN.interpreter
COMPOSER: Composer = BRAIN.composer


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class TextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model: str | None = None


class ChatRequest(TextRequest):
    pass


class InterpretRequest(TextRequest):
    pass


class ComposeRequest(BaseModel):
    recipient: str
    intent: str
    platform: str = "auto"


class AnswerRequest(TextRequest):
    pass


class ReminderRequest(TextRequest):
    pass


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload the model in the background so the first real call is fast.
    llm.warm_up_async()
    yield


app = FastAPI(
    title="ALANA Assistant API",
    version="1.0.0",
    description="HTTP access to ALANA's interpretation, chat, composition, "
    "web and reminder departments.",
    lifespan=lifespan,
)


@app.get("/v1/health")
def health() -> dict[str, Any]:
    """Return service and model availability."""
    return {
        "status": "ok",
        "llm_available": llm.available,
        "contacts": len(INTERPRETER.contacts),
        "actions": sorted(
            {
                *INTERPRETER.contacts,
                "open_app",
                "play_song",
                "pause_song",
                "resume_song",
                "previous_song",
                "next_song",
                "send_message",
                "answer_question",
                "set_reminder",
            }
        ),
    }


@app.get("/v1/contacts")
def contacts() -> dict[str, Any]:
    """List known messaging contacts and their profile names."""
    return {
        "contacts": [
            {"name": name, "relationship": profile.get("relationship")}
            for name, profile in sorted(INTERPRETER.contacts.items())
        ]
    }


@app.get("/v1/actions")
def actions() -> dict[str, Any]:
    """Return the configured action set the interpreter may produce."""
    from brain.interpreter import CONFIGURED_ACTIONS

    return {"actions": sorted(CONFIGURED_ACTIONS)}


@app.post("/v1/interpret")
def interpret(payload: InterpretRequest) -> dict[str, Any]:
    """Return a structured interpretation of *text*."""
    return {"decision": INTERPRETER.interpret(payload.text)}


@app.post("/v1/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    """Return a conversational ALANA reply (no action executed)."""
    return {"reply": BRAIN.chat(payload.text)}


@app.post("/v1/compose")
def compose(payload: ComposeRequest) -> dict[str, Any]:
    """Draft a ready-to-send message for *recipient* conveying *intent*."""
    message = COMPOSER.compose(
        recipient=payload.recipient,
        intent=payload.intent,
        platform=payload.platform,
    )
    return {"recipient": payload.recipient, "platform": payload.platform, "message": message}


@app.post("/v1/answer")
def answer(payload: AnswerRequest) -> dict[str, Any]:
    """Answer *text* using live web context (no GUI involved)."""
    return {"question": payload.text, "answer": get_answer(payload.text)}


@app.post("/v1/reminder/parse")
def parse_reminder(payload: ReminderRequest) -> dict[str, Any]:
    """Parse *text* into reminder text, datetime and repeat frequency."""
    reminder_text, dt, frequency = parse_reminder_request(payload.text)
    return {
        "text": reminder_text,
        "datetime": dt.isoformat(),
        "frequency": frequency,
    }


@app.post("/v1/route")
def route(payload: TextRequest) -> dict[str, Any]:
    """Interpret *text* and explain whether/how it can run over the API."""
    decision = INTERPRETER.interpret(payload.text)
    action = decision.get("action", "none")

    if action in HEADLESS_ACTIONS:
        if action == "get_news":
            from actions.news import get_news

            result = get_news(decision.get("topic"))
        elif action == "read_email":
            from actions.gmail import read_email

            result = read_email(decision.get("query", "newer_than:30d"))
        elif action == "check_calendar":
            from actions.calendar import check_calendar

            result = check_calendar()
        else:
            result = get_answer(payload.text)
        return {
            "decision": decision,
            "execution": "headless",
            "result": result,
        }
    if action in SPOTIFY_ACTIONS:
        return {
            "decision": decision,
            "execution": "spotify",
            "note": "Run via the Spotify Web API on the desktop; a token must "
            "be authenticated first.",
        }
    if action in {"send_message", "set_reminder", "open_app"}:
        return {
            "decision": decision,
            "execution": "gui",
            "note": f"{action!r} requires desktop/browser automation; run it "
            "from the CLI.",
        }
    # "none" and anything else fall back to a chat reply.
    return {
        "decision": decision,
        "execution": "chat",
        "role": "assistant",
        "reply": BRAIN.chat(payload.text),
    }


def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the ALANA HTTP server with uvicorn (blocking)."""
    import uvicorn

    uvicorn.run("src.server.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()
