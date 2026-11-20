# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Python Controller for QML Splash Screen
Loads contents/qml/Splash.qml and closes when the main window renders its first frame.
"""

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication


class SplashScreen(QQuickView):
    """Lightweight Python controller for the QML Splash.qml window."""

    def __init__(self, qml_dir: Path | str, icon_path: Path | str | None = None):
        super().__init__()
        self._closed = False
        self._on_frame = None

        self.setFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setColor(QColor(Qt.GlobalColor.transparent))
        self.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)

        qml_path = Path(qml_dir) / "Splash.qml"
        self.setSource(QUrl.fromLocalFile(str(qml_path)))

        root = self.rootObject()
        if root and icon_path and Path(icon_path).exists():
            root.setProperty("iconSource", QUrl.fromLocalFile(str(icon_path)))

        self._center_on_screen()

    def _center_on_screen(self) -> None:
        """Centers the slim QML splash window on the primary monitor."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = self.width() if self.width() > 0 else 340
            h = self.height() if self.height() > 0 else 160
            x = geo.x() + (geo.width() - w) // 2
            y = geo.y() + (geo.height() - h) // 2
            self.setPosition(QPoint(x, y))

    def set_status(self, text: str) -> None:
        """Updates the status text property in Splash.qml and flushes GUI events."""
        root = self.rootObject()
        if root:
            root.setProperty("statusText", text)
        QApplication.processEvents()

    def finish(self, window=None) -> None:
        """Closes the splash window safely on the main thread after first frame."""

        def close_safely() -> None:
            if self._closed:
                return
            self._closed = True
            root = self.rootObject()
            if root is not None:
                root.setProperty("visible", False)
            self.close()
            self.deleteLater()
            if window is not None and hasattr(window, "requestActivate"):
                window.requestActivate()

        frame_signal = getattr(window, "frameSwapped", None)
        if window is not None and frame_signal is not None:

            def on_frame() -> None:
                try:
                    if self._on_frame is not None:
                        frame_signal.disconnect(self._on_frame)
                except Exception:
                    pass
                QTimer.singleShot(0, close_safely)

            self._on_frame = on_frame
            frame_signal.connect(self._on_frame, Qt.ConnectionType.QueuedConnection)
            QTimer.singleShot(1500, close_safely)
        else:
            close_safely()
