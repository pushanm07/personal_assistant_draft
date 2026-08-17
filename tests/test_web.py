import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actions.web import _fallback_answer, answer_question


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

    def test_who_is_the_ceo_of_chatgpt_uses_context_fact(self) -> None:
        answer = _fallback_answer(
            "who is the ceo of chatgpt",
            "Sam Altman is the CEO of OpenAI, the company behind ChatGPT.",
        )
        self.assertEqual(answer, "sam altman")

    def test_answer_question_uses_direct_fact_when_context_is_empty(self) -> None:
        # Force the offline path (no LLM) so this deterministically exercises the
        # direct-fact fallback regardless of whether a local Ollama is running.
        with patch("actions.web.llm.available", False):
            with patch("actions.web.get_context", return_value=""):
                with patch("builtins.print") as mocked_print:
                    answer = answer_question("who is the ceo of openai")

        self.assertEqual(answer, "sam altman")
        mocked_print.assert_called_once_with("sam altman")


if __name__ == "__main__":
    unittest.main()
