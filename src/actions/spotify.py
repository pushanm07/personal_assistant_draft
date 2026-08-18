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
# Keep compatibility with earlier auth runs that cached tokens under a different
# filename or in the default spotipy location. The web app was already using a
# valid redirect URI; the real bug was that the client ignored the existing cache.
DEFAULT_SPOTIFY_CACHE = PROJECT_ROOT / ".cache"
# Read + modify playback, library, and playlists so every ALANA control works.
SPOTIFY_SCOPES = (
    "user-read-private user-read-playback-state user-modify-playback-state "
    "user-read-currently-playing user-library-read user-library-modify "
    "playlist-read-private playlist-modify-public playlist-modify-private"
)
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


def _load_spotify_config() -> dict:
    """Load config/spotify.json (client id/secret/redirect)."""
    with SPOTIFY_CONFIG.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not all(key in config for key in ("client id", "client secret", "redirect uri")):
        raise ValueError("config/spotify.json must contain 'client id', 'client secret' and 'redirect uri'.")
    return config


def _resolve_token_cache() -> Path | None:
    """Locate an existing Spotify token cache in any standard project path."""
    candidates = [
        TOKEN_CACHE,
        DEFAULT_SPOTIFY_CACHE,
        PROJECT_ROOT / ".cache" / "spotipy",
        Path.home() / ".cache" / "spotipy",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def get_spotify_client() -> "spotipy.Spotify | None":
    """Return the process-wide authenticated Spotify client, building it once.

    The app must respect any existing token cache instead of assuming every
    Spotify session needs a brand-new auth flow. If no cache exists, return none.
    """
    global _spotify_client
    if _spotify_client is not None:
        return _spotify_client

    cache_path = _resolve_token_cache()
    if cache_path is None:
        print("Spotify is not authenticated. Please run 'authenticate_spotify' first.")
        return None

    with _client_lock:
        if _spotify_client is not None:
            return _spotify_client
        spotify_config = _load_spotify_config()
        auth_manager = SpotifyOAuth(
            client_id=spotify_config["client id"],
            client_secret=spotify_config["client secret"],
            redirect_uri=spotify_config["redirect uri"],
            scope=SPOTIFY_SCOPES,
            cache_path=str(cache_path),
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
    """Authorize ALANA to use the Spotify Web API and cache its token.

    Opens the browser and waits for you to approve; paste the final URL back
    into the terminal when your browser lands on the redirect page. The token
    cache is written to ``.spotify_token_cache`` and reused afterwards.
    """
    spotify_config = _load_spotify_config()

    auth_manager = SpotifyOAuth(
        client_id=spotify_config["client id"],
        client_secret=spotify_config["client secret"],
        redirect_uri=spotify_config["redirect uri"],
        scope=SPOTIFY_SCOPES,
        cache_path=str(TOKEN_CACHE),
        open_browser=True,
    )

    try:
        code = auth_manager.get_auth_response()
    except Exception:
        # Manual fallback: browser already open, ask the user to paste the URL.
        print("If your browser did not open, or you were not redirected, paste the")
        print("complete URL from the address bar here:")
        response_url = input("Redirect URL: ").strip()
        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(response_url).query)
        code = query.get("code", [None])[0]
        if not code:
            print("No authorization code found in that URL.")
            return

    token: dict = auth_manager.get_access_token(code)
    if not token:
        print("Spotify authentication failed.")
        return

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


def _pick_or_open_device(spotify: "spotipy.Spotify") -> str | None:
    """Return an active-worthy device id, launching Spotify if none is visible.

    Returns None when no usable playback device exists after one retry.
    """
    def _devices() -> list:
        try:
            return spotify.devices().get("devices", []) or []
        except Exception:
            return []

    devices = _devices()
    if not devices:
        print("Opening Spotify so it can become a playback device...")
        open_spotify()
        time.sleep(4)
        devices = _devices()

    if not devices:
        print("No Spotify playback device is available. Open Spotify, start any song once, then try again.")
        return None

    device = next((item for item in devices if item.get("is_active")), devices[0])
    device_id = device.get("id")
    if not device_id:
        print("Spotify returned a playback device without an ID.")
        return None
    return device_id


def _start_uris(spotify: "spotipy.Spotify", uris: list[str], *, force_play: bool = True) -> bool:
    """Transfer to a device and start playback of the given track URIs."""
    from spotipy import SpotifyException

    try:
        device_id = _pick_or_open_device(spotify)
        if device_id is None:
            return False
        try:
            spotify.start_playback(device_id=device_id, uris=uris)
        except SpotifyException:
            # The device may have lost focus; transfer then retry once.
            spotify.transfer_playback(device_id, force_play=force_play)
            spotify.start_playback(device_id=device_id, uris=uris)
        return True
    except Exception as error:
        print(f"Spotify could not start playback: {error}")
        return False


def _start_context(spotify: "spotipy.Spotify", context_uri: str, *, force_play: bool = True) -> bool:
    """Transfer to a device and start playback of a playlist/album context."""
    from spotipy import SpotifyException

    try:
        device_id = _pick_or_open_device(spotify)
        if device_id is None:
            return False
        try:
            spotify.start_playback(device_id=device_id, context_uri=context_uri)
        except SpotifyException:
            spotify.transfer_playback(device_id, force_play=force_play)
            spotify.start_playback(device_id=device_id, context_uri=context_uri)
        return True
    except Exception as error:
        print(f"Spotify could not start playback: {error}")
        return False


def search_songs(query: str, limit: int = 5) -> list[dict]:
    """Return a compact list of track dicts for *query* (no printing)."""
    spotify = get_spotify_client()
    if spotify is None:
        return []
    try:
        results = spotify.search(q=query, type="track", limit=limit)
    except Exception:
        return []
    tracks: list[dict] = []
    for item in results.get("tracks", {}).get("items", []) or []:
        album = item.get("album") or {}
        images = album.get("images") or []
        tracks.append({
            "uri": item.get("uri"),
            "name": item.get("name", ""),
            "artist": ", ".join(a.get("name", "") for a in item.get("artists", []) or []),
            "album": album.get("name", ""),
            "artwork": images[0].get("url") if images else "",
            "duration_ms": item.get("duration_ms", 0),
        })
    return tracks


def play_playlist(playlist_name: str) -> None:
    """Search for a playlist and start playing it."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    query = playlist_name.strip().removesuffix(" playlist").strip()
    try:
        results = spotify.search(q=query, type="playlist", limit=5)
    except Exception as error:
        print(f"Spotify could not search for playlist '{playlist_name}': {error}")
        return

    playlists = results.get("playlists", {}).get("items", []) or []
    playlists = [p for p in playlists if not (p.get("name") or "").startswith("Discover Weekly")]
    if not playlists:
        print(f"No playlist found for '{playlist_name}'.")
        return

    playlist = playlists[0]
    if _start_context(spotify, playlist["uri"]):
        print(f"Playing playlist '{playlist['name']}'.")


def play_album(album_name: str) -> None:
    """Search for an album and start playing it."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    query = album_name.strip().removesuffix(" album").strip()
    try:
        results = spotify.search(q=query, type="album", limit=5)
    except Exception as error:
        print(f"Spotify could not search for album '{album_name}': {error}")
        return

    albums = results.get("albums", {}).get("items", []) or []
    if not albums:
        print(f"No album found for '{album_name}'.")
        return

    album = albums[0]
    if _start_context(spotify, album["uri"]):
        print(f"Playing album '{album['name']}'.")


def add_song_to_playlist(song_name: str, playlist_name: str) -> None:
    """Search for *song_name* and add it to *playlist_name*."""
    spotify = get_spotify_client()
    if spotify is None:
        return

    title, artist = split_song_and_artist(song_name)
    query = f"track:{title}"
    if artist:
        query += f" artist:{artist}"
    try:
        results = spotify.search(q=query, type="track", limit=10)
        tracks = results.get("tracks", {}).get("items", []) or []
        playlists_res = spotify.search(
            q=playlist_name.strip().removesuffix(" playlist").strip(),
            type="playlist",
            limit=5,
        )
        playlists = playlists_res.get("playlists", {}).get("items", []) or []
    except Exception as error:
        print(f"Spotify could not search for '{song_name}' / '{playlist_name}': {error}")
        return

    if not tracks:
        print(f"No song found for '{song_name}'.")
        return
    if not playlists:
        print(f"No playlist found for '{playlist_name}'.")
        return

    track = choose_track(tracks, title, artist)
    playlist = playlists[0]
    try:
        spotify.playlist_add_items(playlist["id"], [track["uri"]])
    except Exception as error:
        print(f"Spotify could not add the track to the playlist: {error}")
        return

    print(f"Added '{track['name']}' to playlist '{playlist['name']}'.")


def get_playback_state() -> dict | None:
    """Return a compact snapshot for ALANA's music UI, or None if unavailable.

    Print-free on purpose: the desktop bridge polls this without spamming the
    console.
    """
    spotify = get_spotify_client()
    if spotify is None:
        return None
    try:
        playback = spotify.current_playback()
    except Exception:
        return None
    if playback is None:
        return {"playing": False, "title": "", "artist": "", "artwork": "", "progress_ms": 0, "duration_ms": 0}

    item = playback.get("item") or {}
    album = item.get("album") or {}
    images = album.get("images") or []
    artists = item.get("artists") or []
    return {
        "playing": bool(playback.get("is_playing")),
        "title": item.get("name", ""),
        "artist": ", ".join(a.get("name", "") for a in artists),
        "artwork": images[0].get("url") if images else "",
        "progress_ms": playback.get("progress_ms", 0) or 0,
        "duration_ms": item.get("duration_ms", 0) or 0,
        "device": (playback.get("device") or {}).get("name", ""),
    }


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

    
