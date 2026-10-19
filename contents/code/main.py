# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Main Entry Point
Starts PySide6 Application and loads QML interface.
"""

import os
import signal
import sys
from pathlib import Path

# Ensure clean imports from local code directory
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from backend import Backend
from splash import SplashScreen
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMessageBox
from __feature__ import snake_case, true_property

IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_resource_dir() -> Path:
    """Returns directory containing qml and assets, handling PyInstaller sys._MEIPASS."""
    if IS_FROZEN:
        bundle_path = Path(sys._MEIPASS)
        return (
            bundle_path / "contents"
            if (bundle_path / "contents").exists()
            else bundle_path
        )
    return CURRENT_DIR.parent  # contents

if __name__ == "__main__":
    app = QApplication(sys.argv)

    contents_dir = get_resource_dir()
    icon_path = contents_dir / "qml" / "img" / "icon.svg"
    if not icon_path.exists():
        icon_path = contents_dir.parent / "packaging" / "icon.png"
        app.window_icon = QIcon(str(icon_path))

    # Show instant splash screen while QML / Kirigami / backend loads
    splash = SplashScreen(contents_dir / "qml", icon_path)
    splash.show()
    QApplication.process_events()
    splash.set_status("Starting Flow Control...")

    # Close PyInstaller bootloader splash if present
    try:
        import pyi_splash
        if pyi_splash.is_alive():
            pyi_splash.close()
    except (ImportError, AttributeError):
        pass

    if sys.platform.startswith("linux"):
        host_icon_dirs = [
            str(Path.home() / ".local/share/icons"),
            "/usr/share/icons",
            "/usr/local/share/icons",
        ]
        QIcon.set_theme_search_paths(host_icon_dirs + QIcon.theme_search_paths())

    # Append bundled icons at the END of the search paths as a fallback
    bundled_icons = contents_dir / "icons"
    if not bundled_icons.exists() and IS_FROZEN:
        bundled_icons = Path(sys._MEIPASS) / "icons"

    if bundled_icons.exists():
        QIcon.set_theme_search_paths(QIcon.theme_search_paths() + [str(bundled_icons)])
        QIcon.set_fallback_theme_name("breeze-fallback")
    else:
        QIcon.set_fallback_theme_name("breeze")
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    splash.set_status("Initializing backend controller...")
    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.root_context().set_context_property("backend", backend)

    # QML error logging
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

    if IS_FROZEN:
        # In PyInstaller builds, ONLY search inside the bundle to prevent host ABI clashes
        bundle_root = Path(sys._MEIPASS)
        engine.add_import_path(str(bundle_root))
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bundle_root))
    else:
        # development fallbacks
        if sys.platform.startswith("linux"):
            for sys_qml in [
                "/usr/lib/qt6/qml",
                "/usr/lib/x86_64-linux-gnu/qt6/qml",
                "/usr/lib64/qt6/qml",
            ]:
                if Path(sys_qml).exists():
                    engine.add_import_path(sys_qml)
        elif sys.platform == "win32":
            craft_root = Path(os.environ.get("CRAFT_ROOT", r"C:\CraftRoot"))
            if (craft_root / "bin").exists() and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(craft_root / "bin"))
            for qml_sub in ["qml", r"bin\data\qml", r"share\qt6\qml"]:
                if (craft_root / qml_sub).exists():
                    engine.add_import_path(str(craft_root / qml_sub))

    splash.set_status("Loading user interface...")
    qml_file = contents_dir / "qml" / "main.qml"
    if not qml_file.exists():
        qml_file = contents_dir / "qml" / "Main.qml"

    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"

    engine.load(qml_file)

    if not engine.root_objects():
        splash.close()
        detailed_err = (
            "\n".join(qml_errors) if qml_errors else "Unknown QML loading error."
        )
        full_msg = f"[ERROR] Failed to load QML root objects.\n\nQML Diagnostics:\n{detailed_err}"
        print(full_msg, file=sys.stderr)

        try:
            log_path = (
                Path(sys.executable).parent / "FlowControl_startup.log"
                if IS_FROZEN
                else Path("FlowControl_startup.log")
            )
            log_path.write_text(
                f"{full_msg}\n\nImport Paths:\n" + "\n".join(engine.import_path_list()),
                encoding="utf-8",
            )
        except Exception:
            pass

        msg_box = QMessageBox()
        msg_box.icon = QMessageBox.Icon.Critical
        msg_box.window_title = "Flow Control - Startup Error"
        msg_box.text = (
            "Failed to initialize the user interface.\n\n"
            f"{detailed_err}\n\n"
            "Please verify that Kirigami and the required graphics drivers are installed."
        )
        msg_box.exec()
        sys.exit(-1)

    # Automatically dismiss loading window when main window renders its first frame
    main_window = engine.root_objects()[0]
    splash.finish(engine.root_objects()[0])
    app.window_icon = QIcon(str(icon_path))

    # main entry point
    backend.connect()
    sys.exit(app.exec())
