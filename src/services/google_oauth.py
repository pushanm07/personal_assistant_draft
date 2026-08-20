"""Independent OAuth helpers for Google's Gmail and Calendar APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_credentials(
    client_file: Path,
    token_file: Path,
    scopes: Sequence[str],
) -> Credentials:
    """Load, refresh, or create OAuth credentials for one Google service."""
    credentials: Credentials | None = None
    if token_file.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_file), scopes)

    if credentials and credentials.valid:
        return credentials
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), scopes)
        credentials = flow.run_local_server(port=0, open_browser=True)

    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return credentials
