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


if __name__ == "__main__":
    unittest.main()
