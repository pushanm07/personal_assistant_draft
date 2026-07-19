import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actions.web import _fallback_answer


class WebFallbackAnswerTests(unittest.TestCase):
    def test_generic_navigation_text_is_not_returned_as_answer(self) -> None:
        context = "menu live scores schedule archives news series teams videos rankings more"
        answer = _fallback_answer("what is the score in the India vs Australia cricket match?", context)

        self.assertNotIn("menu live scores", answer.lower())
        self.assertTrue(answer.lower().startswith("i couldn't find") or answer.replace(" ", "").isdigit())

    def test_who_has_most_f1_wins_is_answered_directly(self) -> None:
        answer = _fallback_answer("who has the most f1 wins", "Lewis Hamilton holds the record for the most race wins in Formula One history.")
        self.assertEqual(answer, "lewis hamilton")

    def test_who_is_ariana_grande_uses_entity_description(self) -> None:
        answer = _fallback_answer("who is ariana grande", "Ariana Grande is an American singer-songwriter and actress.")
        self.assertIn("ariana grande is", answer.lower())


if __name__ == "__main__":
    unittest.main()
