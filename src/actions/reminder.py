import re
import webbrowser
import time
from datetime import datetime, timedelta
import pyautogui

import dateparser
from dateparser.search import search_dates


def extract_reminder_frequency(text: str | None) -> str:
    if not text:
        return "once"

    normalized = text.lower()
    if re.search(r"\b(every\s+(?:morning|afternoon|evening|night)|daily)\b", normalized):
        return "daily"
    if re.search(r"\b(every\s+(?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|weekly)\b", normalized):
        return "weekly"
    if re.search(r"\b(fortnight|biweekly|every\s+two\s+weeks|every\s+2\s+weeks)\b", normalized):
        return "fortnight"
    if re.search(r"\b(every\s+month|monthly)\b", normalized):
        return "monthly"
    if re.search(r"\b(every\s+year|yearly|annually)\b", normalized):
        return "yearly"
    return "once"


def _has_explicit_time(text: str | None) -> bool:
    if not text:
        return False

    return bool(
        re.search(r"\b\d{1,2}(:\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\b", text, flags=re.IGNORECASE)
        or re.search(r"\b(noon|midnight|morning|afternoon|evening|tonight|night)\b", text, flags=re.IGNORECASE)
    )


def _strip_reminder_command(text: str) -> str:
    # ``\\b`` after the optional (to|for|about) ensures we only strip a whole
    # word -- without it, "Remind me tomorrow" matched " to" and ate the "to"
    # prefix of "tomorrow", leaving "morrow".
    stripped = re.sub(
        r"^\s*(?:remind\s+me|remind|set\s+(?:a\s+)?reminder|reminder)\b(?:\s+(?:to|for|about)\b)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return stripped.strip()


# Words that belong to the schedule region (days, times, their prepositions and
# trailing fillers). Only stripped from the FRONT of the text so reminder
# content elsewhere is never touched.
_SCHEDULE_FRONT = re.compile(
    r"^(?:\s*(?:every\s+)?(?:day|week|month|year|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|today|tomorrow|tonight|morning|afternoon|"
    r"evening|night|noon|midnight|daily|weekly|monthly|yearly|annually|"
    r"fortnight|biweekly|at|on|in|by|to|that|for|about|and|the|a|an|before|"
    r"after|until|till|then|\d{1,2}(?::\d{2})?(?:\s*(?:am|pm|a\.m\.|p\.m\.))?))+",
    re.IGNORECASE,
)


def _strip_schedule_terms(text: str) -> str:
    """Strip the leading schedule region (dates/times/prepositions/fillers)."""
    previous = None
    while previous != text:
        previous = text
        text = _SCHEDULE_FRONT.sub("", text, count=1).lstrip()
    return text



def parse_reminder_request(
    text: str | None,
    now: datetime | None = None,
) -> tuple[str, datetime, str]:
    """Extract reminder text, schedule datetime, and repeat frequency from a phrase."""
    now = now or datetime.now()
    raw_text = (text or "").strip()
    if not raw_text:
        return (
            "Reminder",
            now.replace(hour=9, minute=0, second=0, microsecond=0),
            "once",
        )

    frequency = extract_reminder_frequency(raw_text)
    parsed_dt = None

    try:
        matches = search_dates(
            raw_text,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": now,
            },
        ) or []
    except Exception:
        matches = []

    if matches:
        parsed_dt = matches[0][1]

    if parsed_dt is None:
        parsed_dt = dateparser.parse(
            raw_text,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": now,
            },
        )

    if parsed_dt is None:
        parsed_dt = now + timedelta(days=1)

    if not _has_explicit_time(raw_text):
        default_hour = 9
        if re.search(r"\bmorning\b", raw_text, flags=re.IGNORECASE):
            default_hour = 9
        elif re.search(r"\bafternoon\b", raw_text, flags=re.IGNORECASE):
            default_hour = 15
        elif re.search(r"\b(evening|tonight|night)\b", raw_text, flags=re.IGNORECASE):
            default_hour = 19
        elif re.search(r"\bnoon\b", raw_text, flags=re.IGNORECASE):
            default_hour = 12
        elif re.search(r"\bmidnight\b", raw_text, flags=re.IGNORECASE):
            default_hour = 0

        parsed_dt = parsed_dt.replace(
            hour=default_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if parsed_dt <= now:
            parsed_dt += timedelta(days=1)

    # An explicit "tomorrow" overrides a search that resolved only the time to
    # today (e.g. "tomorrow at 6pm" -> search_dates may return today 18:00).
    if (
        re.search(r"\btomorrow\b", raw_text, flags=re.IGNORECASE)
        and parsed_dt.date() == now.date()
    ):
        parsed_dt += timedelta(days=1)

    # Strip the command prefix, then the leading schedule region (whole-word /
    # front-anchored so reminder content like "tomorrow" in the middle is safe).
    reminder_text = _strip_reminder_command(raw_text)
    reminder_text = _strip_schedule_terms(reminder_text)
    reminder_text = re.sub(r"\s+", " ", reminder_text).strip(" .,:;-")

    if not reminder_text:
        reminder_text = _strip_reminder_command(raw_text) or "Reminder"

    return reminder_text, parsed_dt, frequency


def set_reminder(
    reminder_request: str | None = None,
    reminder_time: str | None = None,
    name: str | None = None,
):
    if reminder_request is None:
        reminder_request = reminder_time

    if reminder_request is None or not reminder_request.strip():
        reminder_request = input("What should I remind you about? ")

    reminder_text, reminder_dt, frequency = parse_reminder_request(reminder_request)
    if not reminder_text:
        reminder_text = name or "Reminder"

    year = str(reminder_dt.year)
    month = f"{reminder_dt.month:02}"
    day = f"{reminder_dt.day:02}"

    hour12 = reminder_dt.strftime("%I")
    minute = reminder_dt.strftime("%M")
    ampm = reminder_dt.strftime("%p")

    webbrowser.open("https://www.icloud.com/reminders/")
    time.sleep(8)

    pyautogui.scroll(-4584)
    time.sleep(0.4)

    pyautogui.click(671, 954)
    time.sleep(0.4)
    pyautogui.write(reminder_text)
    time.sleep(0.4)

    pyautogui.click(1835, 956)
    time.sleep(1)

    pyautogui.click(1420, 710)
    time.sleep(1)

    pyautogui.click(1496, 649)
    time.sleep(1)
    pyautogui.write(year)
    time.sleep(1)

    pyautogui.click(1445, 650)
    time.sleep(1)
    pyautogui.write(day)
    time.sleep(1)

    pyautogui.click(1419, 648)
    time.sleep(1)
    pyautogui.write(month)
    time.sleep(1)

    pyautogui.click(1570, 650)
    time.sleep(1)
    pyautogui.write(hour12)
    time.sleep(1)

    pyautogui.click(1600, 648)
    time.sleep(1)
    pyautogui.write(minute)
    time.sleep(1)

    if ampm == "PM":
        pyautogui.click(1695, 686)
    else:
        pyautogui.click(1696, 654)

    time.sleep(1)

    pyautogui.click(1468, 693)
    time.sleep(1)

    match frequency:
        case "daily":
            pyautogui.click(1468, 726)

        case "weekly":
            pyautogui.click(1468, 759)

        case "fortnight":
            pyautogui.click(1468, 792)

        case "monthly":
            pyautogui.click(1468, 825)

        case "yearly":
            pyautogui.click(1468, 858)

        case _:
            pyautogui.click(1468, 693)
            
    time.sleep(1)
    pyautogui.press("enter")

    pyautogui.hotkey("ctrl", "w")