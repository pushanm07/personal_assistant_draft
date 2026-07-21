import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain.composer import Composer


class ComposerContractTests(unittest.TestCase):
    def test_empty_intent_returns_none(self) -> None:
        composer = Composer()
        self.assertIsNone(composer.compose("zaria", "  "))

    def test_clean_strips_preamble_and_quotes(self) -> None:
        raw = 'Sure, here is the message:\n"hey, running a bit late"'
        self.assertEqual(Composer._clean(raw), "hey, running a bit late")

    def test_fallback_capitalizes_intent(self) -> None:
        self.assertEqual(Composer._fallback("i'm running late"), "I'm running late")

    def test_known_contact_profile_is_loaded(self) -> None:
        composer = Composer()
        # Contacts are lower-cased on load; zaria ships in config/contacts.json.
        self.assertIn("zaria", composer.contacts)


if __name__ == "__main__":
    unittest.main()
