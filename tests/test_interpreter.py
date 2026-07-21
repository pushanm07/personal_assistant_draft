import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain.interpreter import Interpreter


class InterpreterContractTests(unittest.TestCase):
    def test_open_spotify_request_is_interpreted_as_open_app(self) -> None:
        interpreter = Interpreter()
        interpretation = interpreter.interpret("can you open spotfy for me pls")

        self.assertEqual(interpretation["action"], "open_app")
        self.assertEqual(interpretation["target"], "spotify")
        self.assertGreaterEqual(interpretation["confidence"], 0.8)

    def test_message_request_infers_recipient_and_intent(self) -> None:
        interpreter = Interpreter()
        interpretation = interpreter.interpret("whatsapp rohin that i'm running late")

        self.assertEqual(interpretation["action"], "send_message")
        self.assertEqual(interpretation["recipient"], "rohin")
        self.assertEqual(interpretation["platform"], "whatsapp")
        self.assertIn("running late", interpretation["intent"].lower())

    def test_tell_phrasing_is_recognized_with_intent(self) -> None:
        interpreter = Interpreter()
        interpretation = interpreter.interpret("tell zaria im gonna be late")

        self.assertEqual(interpretation["action"], "send_message")
        self.assertEqual(interpretation["recipient"], "zaria")
        self.assertIn("late", interpretation["intent"].lower())

    def test_let_know_phrasing_is_recognized_with_intent(self) -> None:
        interpreter = Interpreter()
        interpretation = interpreter.interpret("let sesha know i landed safe")

        self.assertEqual(interpretation["action"], "send_message")
        self.assertEqual(interpretation["recipient"], "sesha")
        self.assertIn("landed", interpretation["intent"].lower())

    def test_intent_is_not_the_raw_prompt(self) -> None:
        interpreter = Interpreter()
        interpretation = interpreter.interpret("tell chinmay im late")

        # The intent is the gist, stripped of the command framing.
        self.assertNotIn("tell", interpretation["intent"].lower())
        self.assertNotIn("chinmay", interpretation["intent"].lower())


if __name__ == "__main__":
    unittest.main()
