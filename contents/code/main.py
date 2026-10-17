# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Main Entry Point
Starts PySide6 Application and loads QML interface.
Follows KPackage hierarchy.
"""
import sys
import os
import signal
from pathlib import Path

# Ensure clean imports from local code directory
CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(CURRENT_DIR))

from backend import Backend
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from __feature__ import snake_case, true_property


def get_resource_dir() -> Path:
    """Returns directory containing qml and assets, handling PyInstaller sys._MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_path = Path(sys._MEIPASS)
        if (bundle_path / "contents").exists():
            return bundle_path / "contents"
        return bundle_path
    return CURRENT_DIR.parent  # contents/


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    backend = Backend()
    context = engine.root_context()
    context.set_context_property("backend", backend)

    # For theming outside KDE Plasma
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"

    contents_dir = get_resource_dir()
    engine.add_import_path(str(contents_dir))
    engine.add_import_path(str(contents_dir / "qml"))

    qml_file = contents_dir / "qml" / "main.qml"
    if not qml_file.exists():
        qml_file = contents_dir / "qml" / "Main.qml"

    icon_path = contents_dir / "qml" / "img" / "icon.svg"
    if icon_path.exists():
        app.window_icon = QIcon(str(icon_path))

    engine.load(qml_file)

    if not engine.root_objects():
        print("[ERROR] Failed to load QML root objects.", file=sys.stderr)
        sys.exit(-1)

    # main entry point
    backend.connect()
    sys.exit(app.exec())
