"""Spotify-related actions for ALANA."""

import json
import subprocess
import threading
import time
import re
import spotipy
from functools import lru_cache
from pathlib import Path
from spotipy.oauth2 import SpotifyOAuth



PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPS_CONFIG = PROJECT_ROOT / "config" / "apps.json"
SPOTIFY_CONFIG = PROJECT_ROOT / "config" / "spotify.json"
TOKEN_CACHE = PROJECT_ROOT / ".spotify_token_cache"
SPOTIFY_SCOPES = "user-read-private user-library-read user-read-playback-state user-modify-playback-state"
NON_ORIGINAL_MARKERS = ("cover", "tribute", "karaoke", "instrumental")

# A single authenticated client is reused for every command. Building a fresh
# SpotifyOAuth + spotipy client per action meant re-reading config/spotify.json
# and re-running the OAuth token refresh handshake each time, which was the
# dominant cost for pause/play/skip actions.
_spotify_client: "spotipy.Spotify | None" = None
_client_lock = threading.Lock()


@lru_cache(maxsize=None)
def get_app_path(app_name: str) -> Path:
    """Return an application's configured executable path (cached per process)."""
    with APPS_CONFIG.open(encoding="utf-8") as config_file:
        apps = json.load(config_file)

    try:
        return Path(apps[app_name])
    except KeyError as error:
        raise ValueError(f"No path configured for '{app_name}'.") from error


def get_spotify_client() -> "spotipy.Spotify | None":
    """Return the process-wide authenticated Spotify client, building it once.

    Returns ``None`` (and prints a hint) when ALANA is not yet authenticated.
    """
    global _spotify_client
    if _spotify_client is not None:
        return _spotify_client

    if not TOKEN_CACHE.is_file():
        print("Spotify is not authenticated. Please run 'authenticate_spotify' first.")
        return None

    with _client_lock:
        if _spotify_client is not None:
            return _spotify_client
        with SPOTIFY_CONFIG.open(encoding="utf-8") as config_file:
            spotify_config = json.load(config_file)
        auth_manager = SpotifyOAuth(
            client_id=spotify_config["client id"],
            client_secret=spotify_config["client secret"],
            redirect_uri=spotify_config["redirect uri"],
            scope=SPOTIFY_SCOPES,
            cache_path=str(TOKEN_CACHE),
            open_browser=False,
        )
        _spotify_client = spotipy.Spotify(auth_manager=auth_manager)
        return _spotify_client


def open_spotify() -> None:
    """Open Spotify using the path stored in config/apps.json."""
    spotify_path = get_app_path("spotify")

    if not spotify_path.is_file():
        print(f"Spotify was not found at: {spotify_path}")
        return

    subprocess.Popen([str(spotify_path)])
    print("Opening Spotify...")

def authenticate_spotify() -> None:
    """Authorize ALANA to use the Spotify Web API and cache its token."""
    with SPOTIFY_CONFIG.open(encoding="utf-8") as config_file:
        spotify_config = json.load(config_file)

    auth_manager = SpotifyOAuth(
        client_id=spotify_config["client id"],
        client_secret=spotify_config["client secret"],
        redirect_uri=spotify_config["redirect uri"],
        scope=SPOTIFY_SCOPES,
        cache_path=str(TOKEN_CACHE),
        open_browser=True,
    )
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    try:
        profile = spotify.current_user()
    except Exception as error:
        print(f"Spotify authentication failed: {error}")
        return

    print(f"Spotify authenticated for {profile.get('display_name', 'your account')}.")


def get_active_device_id(spotify: spotipy.Spotify) -> str | None:
    """Return the current active playback device, if Spotify reports one."""
    try:
        playback = spotify.current_playback() or {}
        device_id = playback.get("device", {}).get("id")
        if device_id:
            return device_id

        devices = spotify.devices().get("devices", [])
    except Exception as error:
        print(f"Spotify could not find an active playback device: {error}")
        return None

    active_device = next((device for device in devices if device.get("is_active")), None)
    if active_device and active_device.get("id"):
        return active_device["id"]

    print("No active Spotify device is available. Open Spotify and start a track first.")
    return None


def split_song_and_artist(song_name: str) -> tuple[str, str | None]:
    """Support requests such as 'Bad Guy by Billie Eilish'."""
    parts = re.split(r"\s+by\s+", song_name, maxsplit=1, flags=re.IGNORECASE)
    title = parts[0].strip()
    artist = parts[1].strip() if len(parts) == 2 else None
    return title, artist or None


def normalize_text(value: str) -> str:
    """Normalize text for comparing Spotify track metadata."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def choose_track(tracks: list[dict], title: str, artist: str | None) -> dict:
    """Prefer exact, non-cover matches and an explicitly requested artist."""
    normalized_title = normalize_text(title)
    normalized_artist = normalize_text(artist) if artist else ""

    def score(track: dict) -> int:
        track_name = normalize_text(track.get("name", ""))
        artist_names = " ".join(item.get("name", "") for item in track.get("artists", []))
        normalized_track_artists = normalize_text(artist_names)
        track_text = f"{track.get('name', '')} {artist_names}".lower()

        result = int(track.get("popularity", 0))
        if track_name == normalized_title:
            result += 1_000
        elif normalized_title and normalized_title in track_name:
            result += 200
        if normalized_artist and normalized_artist in normalized_track_artists:
            result += 2_000
        if any(marker in track_text for marker in NON_ORIGINAL_MARKERS):
            result -= 2_000
        return result

    return max(tracks, key=score)

def play_song(song_name: str) -> None:
    """Search for a song on Spotify and play it."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    try:
        title, artist = split_song_and_artist(song_name)
        query = f"track:{title}"
        if artist:
            query += f" artist:{artist}"
        results = spotify.search(q=query, type="track", limit=10)
    except Exception as error:
        print(f"Spotify could not search for '{song_name}': {error}")
        return
    tracks = results.get("tracks", {}).get("items", [])

    if not tracks:
        print(f"No results found for '{song_name}'.")
        return

    try:
        devices = spotify.devices().get("devices", [])
    except Exception as error:
        print(f"Spotify could not find a playback device: {error}")
        return

    if not devices:
        print("Opening Spotify so it can become a playback device...")
        open_spotify()
        time.sleep(5)
        try:
            devices = spotify.devices().get("devices", [])
        except Exception as error:
            print(f"Spotify could not find a playback device: {error}")
            return

    if not devices:
        print("No Spotify playback device is available. Open Spotify, start any song once, then try again.")
        return

    device = next((item for item in devices if item.get("is_active")), devices[0])
    device_id = device.get("id")
    if not device_id:
        print("Spotify returned a playback device without an ID.")
        return

    track = choose_track(tracks, title, artist)
    track_uri = track["uri"]
    try:
        if not device.get("is_active"):
            spotify.transfer_playback(device_id, force_play=False)
        spotify.start_playback(device_id=device_id, uris=[track_uri])
    except Exception as error:
        print(f"Spotify could not start playback: {error}")
        return

    print(f"Playing '{track['name']}' by {track['artists'][0]['name']}.")

def pause_song() -> None:
    """Pause the currently playing song on Spotify."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    device_id = get_active_device_id(spotify)
    if not device_id:
        return

    try:
        spotify.pause_playback(device_id=device_id)
    except Exception as error:
        print(f"Spotify could not pause playback: {error}")
        return

    print("Playback paused.")

def resume_song() -> None:
    """Resume the currently paused song on Spotify."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    device_id = get_active_device_id(spotify)
    if not device_id:
        return

    try:
        spotify.start_playback(device_id=device_id)
    except Exception as error:
        print(f"Spotify could not resume playback: {error}")
        return

    print("Playback resumed.")

def next_song() -> None:
    """Skip to the next song on Spotify."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    device_id = get_active_device_id(spotify)
    if not device_id:
        return

    try:
        spotify.next_track(device_id=device_id)
    except Exception as error:
        print(f"Spotify could not skip to the next track: {error}")
        return

    print("Skipped to the next track.")

def previous_song() -> None:
    """Go back to the previous song on Spotify."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    device_id = get_active_device_id(spotify)
    if not device_id:
        return

    try:
        spotify.previous_track(device_id=device_id)
    except Exception as error:
        print(f"Spotify could not go back to the previous track: {error}")
        return

    print("Went back to the previous track.")

    
