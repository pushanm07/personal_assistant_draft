"""ALANA Desktop Application Entry Point.

Launches the PySide6 + QML frontend. The existing Brain remains untouched;
the frontend becomes another interface into Alana.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# Ensure src/ is on sys.path so flat imports (actions.*, brain.*, etc.) work
_SRC = Path(__file__).resolve().parent
# Ensure the package root (src/) is on sys.path so `import app.*` works
# whether the file is run directly or as a module.
_PKG_ROOT = _SRC.parent
for p in (str(_PKG_ROOT), str(_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.config import load_settings, palette_map
from app.ui.controller import AppController


def main() -> int:
    # Must set QQuickStyle before creating QGuiApplication
    QQuickStyle.setStyle("Basic")

    # High-DPI is handled automatically in Qt 6
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QGuiApplication(sys.argv)
    app.setApplicationName("ALANA")
    app.setOrganizationName("AlanaAI")

    settings = load_settings()
    palette = palette_map()

    controller = AppController(settings)

    engine = QQmlApplicationEngine()

    # Expose controller + config to QML
    context = engine.rootContext()
    context.setContextProperty("alana", controller)
    context.setContextProperty("cfg", {
        "window": {
            "width": settings.window.width,
            "height": settings.window.height,
            "minWidth": settings.window.min_width,
            "minHeight": settings.window.min_height,
        },
        "orb": {
            "fpsIdle": settings.orb.fps_idle,
            "fpsActive": settings.orb.fps_active,
            "particleCount": settings.orb.particle_count,
        },
    })
    context.setContextProperty("palette", palette)

    qml_path = _SRC / "ui" / "qml" / "main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("Failed to load QML", file=sys.stderr)
        return 1

    # Graceful shutdown
    def _shutdown() -> None:
        controller.shutdown()

    app.aboutToQuit.connect(_shutdown)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
