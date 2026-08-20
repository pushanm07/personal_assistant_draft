"""Google Calendar service with independent OAuth credentials."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

from services.google_oauth import get_credentials

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_FILE = PROJECT_ROOT / "config" / "calendar_api_client_details.json"
TOKEN_FILE = PROJECT_ROOT / ".google_calendar_token.json"
SCOPES = ("https://www.googleapis.com/auth/calendar.events",)


def _service():
    credentials = get_credentials(CLIENT_FILE, TOKEN_FILE, SCOPES)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def upcoming_events(limit: int = 10) -> list[dict[str, str]]:
    """Return concise upcoming primary-calendar events."""
    now = datetime.now(timezone.utc).isoformat()
    result = _service().events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=max(1, min(limit, 20)),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = []
    for item in result.get("items", []):
        start = item.get("start", {})
        events.append(
            {
                "id": str(item.get("id", "")),
                "summary": str(item.get("summary", "(untitled)")),
                "start": str(start.get("dateTime") or start.get("date") or ""),
                "end": str(item.get("end", {}).get("dateTime") or item.get("end", {}).get("date") or ""),
                "location": str(item.get("location", "")),
                "description": str(item.get("description", ""))[:1000],
            }
        )
    return events


def create_event(
    summary: str,
    start: datetime,
    end: datetime,
    timezone_name: str = "UTC",
    description: str = "",
    location: str = "",
) -> dict[str, str]:
    """Create a validated timed event in the primary calendar."""
    if not summary.strip():
        raise ValueError("An event title is required.")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Event start and end must include a timezone.")
    if end <= start:
        raise ValueError("Event end must be later than its start.")
    body: dict[str, Any] = {
        "summary": summary.strip(),
        "description": description.strip(),
        "location": location.strip(),
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }
    created = _service().events().insert(calendarId="primary", body=body).execute()
    return {
        "id": str(created.get("id", "")),
        "summary": str(created.get("summary", summary.strip())),
        "start": str(created.get("start", {}).get("dateTime", start.isoformat())),
        "html_link": str(created.get("htmlLink", "")),
    }
