# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Main Entry Point
Starts PySide6 Application and loads QML interface.
"""

import os
import signal
import sys
from pathlib import Path

from backend import Backend
from splash import SplashScreen
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMessageBox
from __feature__ import snake_case, true_property

assert snake_case, true_property

# Ensure clean imports from local code directory
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_resource_dir() -> Path:
    """Returns directory containing qml and assets,
    handling PyInstaller sys._MEIPASS."""
    if IS_FROZEN:
        bundle_path = Path(sys._MEIPASS)
        return (
            bundle_path / "contents"
            if (bundle_path / "contents").exists()
            else bundle_path
        )
    return CURRENT_DIR.parent  # contents


def resolve_app_icon(contents_dir: Path) -> Path:
    """Locates the primary application icon."""
    icon_path = contents_dir / "qml" / "img" / "icon.svg"
    if not icon_path.exists():
        icon_path = contents_dir.parent / "packaging" / "icon.png"
    return icon_path


def close_pyinstaller_splash() -> None:
    """Closes the PyInstaller bootloader splash if present."""
    try:
        import pyi_splash

        if pyi_splash.is_alive():
            pyi_splash.close()
    except (ImportError, AttributeError):
        pass


def configure_icon_themes(contents_dir: Path) -> None:
    """Sets up host and bundled fallback icon search paths."""
    if sys.platform.startswith("linux"):
        host_icon_dirs = [
            str(Path.home() / ".local/share/icons"),
            "/usr/share/icons",
            "/usr/local/share/icons",
        ]
        QIcon.set_theme_search_paths(
            host_icon_dirs + QIcon.theme_search_paths()
        )

    # Append bundled icons at the END of the search paths as a fallback
    bundled_icons = contents_dir / "icons"
    if not bundled_icons.exists() and IS_FROZEN:
        bundled_icons = Path(sys._MEIPASS) / "icons"

    if bundled_icons.exists():
        QIcon.set_theme_search_paths(
            QIcon.theme_search_paths() + [str(bundled_icons)]
        )
        QIcon.set_fallback_theme_name("breeze-fallback")
    else:
        QIcon.set_fallback_theme_name("breeze")
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def add_dev_qml_paths(engine: QQmlApplicationEngine) -> None:
    """Adds OS-specific QML import paths for non-frozen development runs."""
    if sys.platform.startswith("linux"):
        linux_paths = [
            "/usr/lib/qt6/qml",
            "/usr/lib/x86_64-linux-gnu/qt6/qml",
            "/usr/lib64/qt6/qml",
        ]
        for sys_qml in linux_paths:
            if Path(sys_qml).exists():
                engine.add_import_path(sys_qml)
    elif sys.platform == "win32":
        craft_root = Path(os.environ.get("CRAFT_ROOT", r"C:\CraftRoot"))
        if (craft_root / "bin").exists() and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(craft_root / "bin"))
        for qml_sub in ["qml", r"bin\data\qml", r"share\qt6\qml"]:
            if (craft_root / qml_sub).exists():
                engine.add_import_path(str(craft_root / qml_sub))


def configure_qml_paths(
    engine: QQmlApplicationEngine, contents_dir: Path
) -> None:
    """Configures QML module import paths for frozen and dev environments."""
    engine.add_import_path(str(contents_dir))
    engine.add_import_path(str(contents_dir / "qml"))

    if IS_FROZEN:
        bundle_root = Path(sys._MEIPASS)
        engine.add_import_path(str(bundle_root))
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bundle_root))
    else:
        add_dev_qml_paths(engine)


def resolve_qml_entry(contents_dir: Path) -> Path:
    """Returns the main QML file path."""
    qml_file = contents_dir / "qml" / "main.qml"
    if not qml_file.exists():
        qml_file = contents_dir / "qml" / "Main.qml"
    return qml_file


def handle_startup_error(
    engine: QQmlApplicationEngine, qml_errors: list[str]
) -> None:
    """Logs diagnostic details, shows a critical alert, and exits."""
    detailed_err = "\n".join(qml_errors) if qml_errors else "Unknown QML loading error."
    full_msg = (
        f"[ERROR] Failed to load QML root objects.\n\nQML Diagnostics:\n{detailed_err}"
    )
    print(full_msg, file=sys.stderr)

    try:
        log_path = (
            Path(sys.executable).parent / "FlowControl_startup.log"
            if IS_FROZEN
            else Path("FlowControl_startup.log")
        )
        import_paths = "\n".join(engine.import_path_list())
        log_path.write_text(
            f"{full_msg}\n\nImport Paths:\n{import_paths}",
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
        "Please verify that Kirigami and the required graphics drivers "
        "are installed."
    )
    msg_box.exec()
    sys.exit(-1)


def main() -> None:
    """Bootstrapper"""

    # platform styling
    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
        if sys.platform == "win32":
            os.environ["QT_QUICK_CONTROLS_STYLE"] = "FluentWinUI3"

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    QApplication.organization_domain = "com.uvr"
    QApplication.organization_name = "Uvic Rocketry"
    QApplication.application_name = "fcs-client"

    contents_dir = get_resource_dir()
    icon_path = resolve_app_icon(contents_dir)
    app.window_icon = QIcon(str(icon_path))

    splash = SplashScreen(contents_dir / "qml", icon_path)
    splash.show()
    QApplication.process_events()
    splash.set_status("Starting Flow Control...")

    close_pyinstaller_splash()
    configure_icon_themes(contents_dir)

    splash.set_status("Initializing backend controller...")
    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.root_context().set_context_property("backend", backend)

    qml_errors: list[str] = []

    def on_qml_warning(warnings):
        for w in warnings:
            msg = w.to_string() if hasattr(w, "to_string") else str(w)
            qml_errors.append(msg)
            print(f"[QML] {msg}", file=sys.stderr)

    engine.warnings.connect(on_qml_warning)
    configure_qml_paths(engine, contents_dir)

    splash.set_status("Loading user interface...")
    engine.load(resolve_qml_entry(contents_dir))

    if not engine.root_objects():
        splash.close()
        handle_startup_error(engine, qml_errors)

    main_window = engine.root_objects()[0]
    splash.finish(main_window)

    backend.connect()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
