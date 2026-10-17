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
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
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
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    backend = Backend()
    context = engine.root_context()
    context.set_context_property("backend", backend)

    # Capture any QML warnings and errors for diagnostics
    qml_errors = []
    def on_qml_warning(warnings):
        for w in warnings:
            msg = w.to_string() if hasattr(w, "to_string") else str(w)
            qml_errors.append(msg)
            print(f"[QML] {msg}", file=sys.stderr)
    engine.warnings.connect(on_qml_warning)

    contents_dir = get_resource_dir()
    engine.add_import_path(str(contents_dir))
    engine.add_import_path(str(contents_dir / "qml"))

    # If running inside PyInstaller bundle, add bundle root and PySide6 QML directory
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        engine.add_import_path(str(bundle_root))
        pyside_qml = bundle_root / "PySide6" / "Qt" / "qml"
        if pyside_qml.exists():
            engine.add_import_path(str(pyside_qml))
        # Ensure Windows searches bundle root for C++ plugins and dependent DLLs
        if sys.platform == "win32":
            os.environ["PATH"] = str(bundle_root) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(bundle_root))
                except Exception:
                    pass

    # Add standard Linux system Qt6 QML module paths as fallbacks
    for sys_qml in [
        "/usr/lib/qt6/qml",
        "/usr/lib/x86_64-linux-gnu/qt6/qml",
        "/usr/lib64/qt6/qml",
    ]:
        if Path(sys_qml).exists():
            engine.add_import_path(sys_qml)

    # On Windows, register KDE Craft installation paths if present
    if sys.platform == "win32":
        craft_root = Path(os.environ.get("CRAFT_ROOT", r"C:\CraftRoot"))
        craft_bin = craft_root / "bin"
        if craft_bin.exists():
            os.environ["PATH"] = str(craft_bin) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(craft_bin))
                except Exception:
                    pass
        for qml_sub in ["qml", r"bin\qml", r"lib\qml", r"share\qt6\qml", r"bin\data\qml", r"share\qml"]:
            cand = craft_root / qml_sub
            if cand.exists():
                engine.add_import_path(str(cand))

    # Force Kirigami desktop style (org.kde.desktop)
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"

    qml_file = contents_dir / "qml" / "main.qml"
    if not qml_file.exists():
        qml_file = contents_dir / "qml" / "Main.qml"

    icon_path = contents_dir / "qml" / "img" / "icon.svg"
    if icon_path.exists():
        app.window_icon = QIcon(str(icon_path))

    engine.load(qml_file)

    if not engine.root_objects():
        err_header = "[ERROR] Failed to load QML root objects."
        detailed_err = "\n".join(qml_errors) if qml_errors else "Unknown QML loading error."
        full_msg = f"{err_header}\n\nQML Diagnostics:\n{detailed_err}"
        print(full_msg, file=sys.stderr)
        
        # Write to log file next to binary for post-mortem inspection
        try:
            log_path = Path("FlowControl_startup.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(full_msg)
                f.write("\n\nImport Paths:\n" + "\n".join(engine.import_path_list()))
        except Exception:
            pass

        try:
            msg_box = QMessageBox()
            msg_box.icon = QMessageBox.Icon.Critical
            msg_box.window_title = "Flow Control - Startup Error"
            msg_box.text = (
                "Failed to initialize the user interface.\n\n"
                f"{detailed_err}\n\n"
                "Please verify that Kirigami and the required graphics drivers are installed."
            )
            msg_box.exec()
        except Exception:
            pass
        sys.exit(-1)

    # main entry point
    backend.connect()
    sys.exit(app.exec())
