import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from internet import fetch


class FetchCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        fetch._cache.clear()

    def test_second_download_hits_cache(self) -> None:
        with patch.object(fetch, "_download_once", return_value="<html>hi</html>") as mock_get:
            first = fetch.download("http://example.com/a")
            second = fetch.download("http://example.com/a")

        self.assertEqual(first, "<html>hi</html>")
        self.assertEqual(second, "<html>hi</html>")
        # Only one network attempt; the second call came back from the cache.
        mock_get.assert_called_once()

    def test_failure_is_cached_as_none(self) -> None:
        with patch.object(fetch, "_download_once", return_value=None):
            self.assertIsNone(fetch.download("http://example.com/bad"))

        # Still cached: no retry on the immediate repeat.
        with patch.object(fetch, "_download_once", return_value="<html>x</html>") as mock_get:
            result = fetch.download("http://example.com/bad")
        self.assertIsNone(result)
        mock_get.assert_not_called()

    def test_distinct_urls_are_not_shared(self) -> None:
        with patch.object(
            fetch, "_download_once", side_effect=lambda url, timeout: f"<{url}>"
        ) as mock_get:
            a = fetch.download("http://example.com/a")
            b = fetch.download("http://example.com/b")
        self.assertEqual(a, "<http://example.com/a>")
        self.assertEqual(b, "<http://example.com/b>")
        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
