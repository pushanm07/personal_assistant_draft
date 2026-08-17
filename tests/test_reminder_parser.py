import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actions.reminder import parse_reminder_request


class ReminderParserTests(unittest.TestCase):
    def test_parses_reminder_text_and_date_with_time(self) -> None:
        reminder_text, reminder_dt, frequency = parse_reminder_request(
            "Remind me tomorrow at 6pm to call mom",
            now=datetime(2026, 7, 21, 10, 0),
        )

        self.assertEqual(reminder_text.lower(), "call mom")
        self.assertEqual(reminder_dt.year, 2026)
        self.assertEqual(reminder_dt.month, 7)
        self.assertEqual(reminder_dt.day, 22)
        self.assertEqual(reminder_dt.hour, 18)
        self.assertEqual(frequency, "once")

    def test_parses_repeat_frequency(self) -> None:
        reminder_text, reminder_dt, frequency = parse_reminder_request(
            "Remind me every Monday at 9 to submit the report",
            now=datetime(2026, 7, 21, 10, 0),
        )

        self.assertEqual(reminder_text.lower(), "submit the report")
        self.assertEqual(frequency, "weekly")
        self.assertEqual(reminder_dt.hour, 9)

    def test_defaults_to_morning_when_only_day_is_given(self) -> None:
        reminder_text, reminder_dt, frequency = parse_reminder_request(
            "remind me on friday to buy groceries",
            now=datetime(2026, 7, 21, 10, 0),
        )

        self.assertEqual(reminder_text.lower(), "buy groceries")
        self.assertEqual(frequency, "once")
        self.assertEqual(reminder_dt.hour, 9)


if __name__ == "__main__":
    unittest.main()
