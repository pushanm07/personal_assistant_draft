"""Spotify-related actions for ALANA."""

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPS_CONFIG = PROJECT_ROOT / "config" / "apps.json"


def get_app_path(app_name: str) -> Path:
    """Return an application's configured executable path."""
    with APPS_CONFIG.open(encoding="utf-8") as config_file:
        apps = json.load(config_file)

    try:
        return Path(apps[app_name])
    except KeyError as error:
        raise ValueError(f"No path configured for '{app_name}'.") from error


def open_spotify() -> None:
    """Open Spotify using the path stored in config/apps.json."""
    spotify_path = get_app_path("spotify")

    if not spotify_path.is_file():
        print(f"Spotify was not found at: {spotify_path}")
        return

    subprocess.Popen([str(spotify_path)])
    print("Opening Spotify...")
