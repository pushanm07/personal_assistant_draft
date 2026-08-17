"""Allow ``python -m src.server`` to launch the ALANA HTTP API."""

from .app import run

if __name__ == "__main__":
    run()
