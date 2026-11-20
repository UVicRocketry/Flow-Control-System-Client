# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Main Entry Point
Starts PySide6 Application and loads QML interface.
"""

import os
import signal
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMessageBox

from splash import SplashScreen

# Ensure clean imports from local code directory
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
IS_APPIMAGE = bool(
    os.environ.get("APPIMAGE")
    or os.environ.get("SHARUN_DIR")
    or os.environ.get("APPDIR")
)
IS_PACKAGED = IS_FROZEN or IS_APPIMAGE


def get_resource_dir() -> Path:
    """Returns directory containing qml and assets, handling PyInstaller."""
    if IS_FROZEN:
        bundle_path = Path(sys._MEIPASS)
        return (
            bundle_path / "contents"
            if (bundle_path / "contents").exists()
            else bundle_path
        )
    return CURRENT_DIR.parent


def resolve_app_icon(contents_dir: Path) -> Path:
    """Locates the primary application icon."""
    icon_path = contents_dir / "qml" / "img" / "icon.svg"
    if not icon_path.exists():
        icon_path = contents_dir.parent / "packaging" / "icon.png"
    return icon_path


def _select_bundled_theme_name(
    bundled_icons: Path, scheme: Qt.ColorScheme | None = None
) -> str:
    """Returns bundled icon theme name ('breeze-fallback-light' or 'breeze-fallback')."""
    if scheme is None:
        scheme = QGuiApplication.styleHints().colorScheme()
    is_light = scheme == Qt.ColorScheme.Light or (
        scheme == Qt.ColorScheme.Unknown
        and QGuiApplication.palette().window().color().lightness() > 128
    )
    if is_light and (bundled_icons / "breeze-fallback-light").exists():
        return "breeze-fallback-light"
    return "breeze-fallback"


def _configure_win_icon_themes(bundled_icons: Path) -> None:
    if not bundled_icons.exists():
        QIcon.setThemeName("breeze")
        QIcon.setFallbackThemeName("breeze")
        return

    QIcon.setThemeSearchPaths([str(bundled_icons)])
    theme_name = _select_bundled_theme_name(bundled_icons)
    QIcon.setThemeName(theme_name)
    QIcon.setFallbackThemeName(theme_name)

    def _on_color_scheme_changed(scheme: Qt.ColorScheme) -> None:
        new_theme = _select_bundled_theme_name(bundled_icons, scheme)
        QIcon.setThemeName(new_theme)
        QIcon.setFallbackThemeName(new_theme)

    QGuiApplication.styleHints().colorSchemeChanged.connect(
        _on_color_scheme_changed
    )


def _configure_unix_icon_themes(bundled_icons: Path) -> None:
    if sys.platform.startswith("linux"):
        host_icon_dirs = [
            str(Path.home() / ".local/share/icons"),
            "/usr/share/icons",
            "/usr/local/share/icons",
        ]
        QIcon.setThemeSearchPaths(host_icon_dirs + QIcon.themeSearchPaths())

    if not bundled_icons.exists():
        QIcon.setFallbackThemeName("breeze")
        return

    QIcon.setThemeSearchPaths(QIcon.themeSearchPaths() + [str(bundled_icons)])
    theme_name = _select_bundled_theme_name(bundled_icons)
    if not QIcon.themeName():
        QIcon.setThemeName(theme_name)
    QIcon.setFallbackThemeName(theme_name)
    QIcon.setFallbackSearchPaths([str(bundled_icons / theme_name / "flat")])

    def _on_color_scheme_changed(scheme: Qt.ColorScheme) -> None:
        new_theme = _select_bundled_theme_name(bundled_icons, scheme)
        if QIcon.themeName() in ("", "breeze-fallback", "breeze-fallback-light"):
            QIcon.setThemeName(new_theme)
        QIcon.setFallbackThemeName(new_theme)
        QIcon.setFallbackSearchPaths([str(bundled_icons / new_theme / "flat")])

    QGuiApplication.styleHints().colorSchemeChanged.connect(
        _on_color_scheme_changed
    )


def configure_icon_themes(contents_dir: Path) -> None:
    """Sets up host and bundled fallback icon search paths."""
    bundled_icons = contents_dir / "icons"
    if not bundled_icons.exists() and IS_FROZEN:
        bundled_icons = Path(sys._MEIPASS) / "icons"

    if sys.platform == "win32":
        _configure_win_icon_themes(bundled_icons)
    else:
        _configure_unix_icon_themes(bundled_icons)

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
                engine.addImportPath(sys_qml)
    elif sys.platform == "win32":
        env_root = Path(os.environ.get("CRAFT_ROOT") or sys.prefix)
        if (env_root / "bin").exists() and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(env_root / "bin"))
        for qml_sub in ("qml", r"bin\data\qml", r"share\qt6\qml"):
            if (env_root / qml_sub).exists():
                engine.addImportPath(str(env_root / qml_sub))


def configure_qml_paths(
    engine: QQmlApplicationEngine, contents_dir: Path
) -> None:
    """Configures QML module import paths for frozen and dev environments."""
    engine.addImportPath(str(contents_dir))
    engine.addImportPath(str(contents_dir / "qml"))

    if IS_FROZEN:
        bundle_root = Path(sys._MEIPASS)
        engine.addImportPath(str(bundle_root))
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bundle_root))
    elif not IS_PACKAGED:
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
    detailed_err = (
        "\n".join(qml_errors) if qml_errors else "Unknown QML loading error."
    )
    full_msg = (
        f"[ERROR] Failed to load QML root objects.\n\nQML Diagnostics:\n{detailed_err}"
    )
    print(full_msg, file=sys.stderr)

    try:
        if IS_PACKAGED:
            default_state = Path.home() / ".local" / "state"
            state_root = Path(os.environ.get("XDG_STATE_HOME", default_state))
            state_dir = state_root / "fcs-client"
            state_dir.mkdir(parents=True, exist_ok=True)
            log_path = state_dir / "FlowControl_startup.log"
        else:
            log_path = Path("FlowControl_startup.log")
        import_paths = "\n".join(engine.importPathList())
        log_path.write_text(
            f"{full_msg}\n\nImport Paths:\n{import_paths}",
            encoding="utf-8",
        )
    except Exception:
        try:
            fallback_log = Path(tempfile.gettempdir()) / "FlowControl_startup.log"
            fallback_log.write_text(full_msg, encoding="utf-8")
        except Exception:
            pass

    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle("Flow Control - Startup Error")
    msg_box.setText(
        "Failed to initialize the user interface.\n\n"
        f"{detailed_err}\n\n"
        "Please verify that Kirigami and the required graphics drivers "
        "are installed."
    )
    msg_box.exec()
    sys.exit(-1)


def main() -> None:
    """Bootstrapper"""
    contents_dir = get_resource_dir()

    # Expose contents/icons to KIconLoader before QApplication init
    if sys.platform.startswith("linux"):
        xdg_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
        if str(contents_dir) not in xdg_dirs.split(":"):
            os.environ["XDG_DATA_DIRS"] = f"{xdg_dirs}:{contents_dir}"

    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        style = "FluentWinUI3" if sys.platform == "win32" else "org.kde.desktop"
        os.environ["QT_QUICK_CONTROLS_STYLE"] = style

    if os.environ.get("QML_DEBUG") or any(
        "-qmljsdebugger" in arg for arg in sys.argv
    ):
        from PySide6.QtQml import QQmlDebuggingEnabler

        QQmlDebuggingEnabler.enableDebugging(True)

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    QApplication.setOrganizationDomain("com.uvr")
    QApplication.setOrganizationName("Uvic Rocketry")
    QApplication.setApplicationName("fcs-client")

    icon_path = resolve_app_icon(contents_dir)
    app.setWindowIcon(QIcon(str(icon_path)))

    splash = SplashScreen(contents_dir / "qml", icon_path)
    splash.show()
    QApplication.processEvents()
    splash.set_status("Starting Flow Control...")

    configure_icon_themes(contents_dir)

    splash.set_status("Initializing backend controller...")
    engine = QQmlApplicationEngine()

    from backend import Backend

    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)

    qml_errors: list[str] = []

    def on_qml_warning(warnings) -> None:
        for w in warnings:
            msg = w.toString() if hasattr(w, "toString") else str(w)
            qml_errors.append(msg)
            print(f"[QML] {msg}", file=sys.stderr)

    engine.warnings.connect(on_qml_warning)
    configure_qml_paths(engine, contents_dir)

    splash.set_status("Loading user interface...")
    engine.load(resolve_qml_entry(contents_dir))

    if not engine.rootObjects():
        splash.close()
        handle_startup_error(engine, qml_errors)

    main_window = engine.rootObjects()[0]
    splash.finish(main_window)

    backend.connect()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
