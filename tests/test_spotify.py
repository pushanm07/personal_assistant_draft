import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actions import spotify


class SpotifyPureFunctionTests(unittest.TestCase):
    def test_split_song_and_artist(self) -> None:
        title, artist = spotify.split_song_and_artist("Bad Guy by Billie Eilish")
        self.assertEqual(title, "Bad Guy")
        self.assertEqual(artist, "Billie Eilish")

    def test_split_without_artist(self) -> None:
        title, artist = spotify.split_song_and_artist("Overdrive")
        self.assertEqual(title, "Overdrive")
        self.assertIsNone(artist)

    def test_choose_track_prefers_exact_and_original(self) -> None:
        tracks = [
            {"name": "Bad Guy", "artists": [{"name": "Billie Eilish"}], "popularity": 90},
            {"name": "Bad Guy (cover)", "artists": [{"name": "Random"}], "popularity": 95},
            {"name": "Bad Guy", "artists": [{"name": "Other"}], "popularity": 99},
        ]
        chosen = spotify.choose_track(tracks, "Bad Guy", "Billie Eilish")
        self.assertEqual(chosen["artists"][0]["name"], "Billie Eilish")

    def test_get_app_path_is_cached(self) -> None:
        path = spotify.get_app_path("spotify")
        self.assertIsInstance(path, Path)
        # lru_cache: the second call returns the same object, no re-read.
        self.assertIs(spotify.get_app_path("spotify"), path)

    def test_get_spotify_client_returns_none_when_unauthenticated(self) -> None:
        spotify._spotify_client = None
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                type(spotify.TOKEN_CACHE),
                "is_file",
                return_value=False,
            ):
                client = spotify.get_spotify_client()
        self.assertIsNone(client)


if __name__ == "__main__":
    unittest.main()
