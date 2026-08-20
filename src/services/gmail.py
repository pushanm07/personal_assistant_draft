"""Gmail API service with independent OAuth credentials."""

from __future__ import annotations

import base64
import html
import re
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

from services.google_oauth import get_credentials

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_FILE = PROJECT_ROOT / "config" / "gmail_api_client_details.json"
TOKEN_FILE = PROJECT_ROOT / ".google_gmail_token.json"
SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
)


def _service():
    credentials = get_credentials(CLIENT_FILE, TOKEN_FILE, SCOPES)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _decode_part(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
        "utf-8", errors="replace"
    )
    if part.get("mimeType") == "text/html":
        decoded = re.sub(r"<[^>]+>", " ", decoded)
        decoded = html.unescape(decoded)
    return re.sub(r"\s+", " ", decoded).strip()


def _body(payload: dict[str, Any]) -> str:
    if payload.get("body", {}).get("data"):
        return _decode_part(payload)
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            text = _decode_part(part)
            if text:
                return text
    for part in payload.get("parts", []):
        text = _body(part)
        if text:
            return text
    return ""


def _clean_message(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload", {})
    headers = {header.get("name", "").lower(): header.get("value", "") for header in payload.get("headers", [])}
    return {
        "id": str(message.get("id", "")),
        "thread_id": str(message.get("threadId", "")),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": re.sub(r"\s+", " ", str(message.get("snippet", ""))).strip(),
        "body": _body(payload)[:6000],
    }


def list_recent(query: str = "", limit: int = 10) -> list[dict[str, str]]:
    """Return cleaned recent Gmail messages; use ``is:unread`` for unread mail."""
    result = _service().users().messages().list(
        userId="me", q=query, maxResults=max(1, min(limit, 20))
    ).execute()
    messages = []
    service = _service()
    for item in result.get("messages", []):
        raw = service.users().messages().get(
            userId="me", id=item["id"], format="full"
        ).execute()
        messages.append(_clean_message(raw))
    return messages


def get_message(message_id: str) -> dict[str, str]:
    """Return one cleaned Gmail message by id."""
    raw = _service().users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()
    return _clean_message(raw)


def _raw_message(recipient: str, subject: str, body: str, thread_id: str | None = None) -> dict[str, str]:
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = recipient
    message["subject"] = subject
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    raw: dict[str, str] = {"raw": encoded}
    if thread_id:
        raw["threadId"] = thread_id
    return raw


def create_draft(recipient: str, subject: str, body: str, thread_id: str | None = None) -> str:
    result = _service().users().drafts().create(
        userId="me", body={"message": _raw_message(recipient, subject, body, thread_id)}
    ).execute()
    return str(result.get("id", ""))


def send_message(recipient: str, subject: str, body: str, thread_id: str | None = None) -> str:
    result = _service().users().messages().send(
        userId="me", body=_raw_message(recipient, subject, body, thread_id)
    ).execute()
    return str(result.get("id", ""))


def reply_to_message(message_id: str, body: str) -> str:
    message = get_message(message_id)
    subject = message["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    return send_message(message["from"], subject, body, message["thread_id"])
