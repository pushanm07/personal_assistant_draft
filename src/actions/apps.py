"""Actions for launching configured desktop applications."""

import subprocess

from .spotify import get_app_path


def open_application(app_name: str, display_name: str) -> None:
    """Open an application using its path from config/apps.json."""
    app_path = get_app_path(app_name)

    if not app_path.is_file():
        print(f"{display_name} was not found at: {app_path}")
        return

    subprocess.Popen([str(app_path)])
    print(f"Opening {display_name}...")


def open_chrome() -> None:
    """Open Google Chrome."""
    open_application("chrome", "Chrome")


def open_vscode() -> None:
    """Open Visual Studio Code."""
    open_application("vscode", "VS Code")
