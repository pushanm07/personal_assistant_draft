"""Tests for the shared Ollama client's token ceiling configuration."""

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain import llm


class TokenCeilingTests(unittest.TestCase):
    """Verify that per-use-case output ceilings are set sensibly."""

    def test_response_paths_have_a_higher_ceiling_than_short_paths(self) -> None:
        """Summarise/chat/answer need room; compose/intent stay deliberately short."""
        self.assertGreater(llm.MAX_CHAT_TOKENS, llm.MAX_COMPOSE_TOKENS)
        self.assertGreater(llm.MAX_ANSWER_TOKENS, llm.MAX_COMPOSE_TOKENS)
        self.assertGreater(llm.MAX_CHAT_TOKENS, llm.MAX_INTENT_TOKENS)
        self.assertGreater(llm.MAX_ANSWER_TOKENS, llm.MAX_INTENT_TOKENS)

    def test_chat_and_answer_ceilings_are_above_summary_threshold(self) -> None:
        """256 tokens was too low for a movie summary; 512 gives headroom."""
        for ceiling in (llm.MAX_CHAT_TOKENS, llm.MAX_ANSWER_TOKENS):
            self.assertGreaterEqual(ceiling, 512)

    def test_short_output_paths_still_use_small_ceilings(self) -> None:
        """Message drafting and intent classification stay snappy by design."""
        self.assertLessEqual(llm.MAX_COMPOSE_TOKENS, 200)
        self.assertLessEqual(llm.MAX_INTENT_TOKENS, 200)

    def test_chat_default_num_predict_matches_answer_ceiling(self) -> None:
        """The fallback default should be the generous answer ceiling, not 256."""
        sig = inspect.signature(llm.chat)
        self.assertEqual(sig.parameters["num_predict"].default, llm.MAX_ANSWER_TOKENS)
