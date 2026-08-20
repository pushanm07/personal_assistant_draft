"""Google Calendar actions for ALANA."""

from __future__ import annotations

from datetime import datetime, timedelta
import re

from services.calendar import create_event, upcoming_events


def check_calendar(limit: int = 10) -> str:
    """Return a concise upcoming schedule from the primary calendar."""
    events = upcoming_events(limit)
    if not events:
        return "There are no upcoming events on your primary calendar, Sir."
    return "\n".join(
        f"{event['summary']} starts {event['start']}"
        + (f" at {event['location']}" if event["location"] else "")
        for event in events
    )


def create_calendar_event(request: str) -> str:
    """Create only fully specified ISO-date events; otherwise ask for detail."""
    match = re.fullmatch(
        r"\s*(?:create|schedule)\s+(?:an?\s+)?event\s+(?:called\s+|named\s+)?(.+?)\s+"
        r"on\s+(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}:\d{2})\s+for\s+(\d+)\s+minutes\s*",
        request,
        flags=re.IGNORECASE,
    )
    if not match:
        return "Please provide the event title, date as YYYY-MM-DD, start time, and duration in minutes, Sir."
    summary, date_text, time_text, duration_text = match.groups()
    try:
        start = datetime.fromisoformat(f"{date_text}T{time_text}:00+00:00")
        end = start + timedelta(minutes=int(duration_text))
    except ValueError:
        return "That date or time is invalid. Please use YYYY-MM-DD and HH:MM, Sir."
    created = create_event(summary, start, end)
    return f"Created {created['summary']} for {created['start']}, Sir."
