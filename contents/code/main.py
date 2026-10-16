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
from backend import Backend

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from __feature__ import snake_case, true_property

# Ensure clean imports from local code directory
CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = CURRENT_DIR.parent.parent
sys.path.insert(0, str(CURRENT_DIR))

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

    qml_file = CURRENT_DIR.parent / "qml" / "main.qml"
    if not qml_file.exists():
        qml_file = CURRENT_DIR.parent / "qml" / "Main.qml"

    icon_path = qml_file.parent / "img" / "icon.svg"
    if icon_path.exists():
        app.window_icon = QIcon(str(icon_path))

    engine.load(qml_file)

    if not engine.root_objects():
        print("[ERROR] Failed to load QML root objects.", file=sys.stderr)
        sys.exit(-1)

    # main entry point
    backend.connect()
    sys.exit(app.exec())
