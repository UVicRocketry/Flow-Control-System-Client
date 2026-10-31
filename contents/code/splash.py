# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Python Controller for QML Splash Screen
Loads contents/qml/Splash.qml and closes when the main window renders its first frame.
"""

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import Qt, QUrl, QTimer, QPoint
from __feature__ import snake_case, true_property

assert snake_case, true_property

class SplashScreen(QQuickView):
    """Lightweight Python controller for the QML Splash.qml window."""

    def __init__(self, qml_dir: Path | str, icon_path: Path | str | None = None):
        super().__init__()
        self._closed = False

        # Frameless, translucent, stay-on-top splash window
        self.flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.color = QColor(Qt.GlobalColor.transparent)
        self.resize_mode = QQuickView.ResizeMode.SizeViewToRootObject

        qml_path = Path(qml_dir) / "Splash.qml"

        self.source = QUrl.from_local_file(str(qml_path))

        # Pass custom icon URL if provided
        root = self.root_object()
        if root and icon_path and Path(icon_path).exists():
            root.set_property("iconSource", QUrl.from_local_file(str(icon_path)))

        self._center_on_screen()

    def _center_on_screen(self):
        """Centers the slim QML splash window on the primary monitor."""
        screen = QGuiApplication.primary_screen
        if callable(screen):
            screen = screen()
        if screen:
            geo = screen.available_geometry
            w = self.width if self.width > 0 else 340
            h = self.height if self.height > 0 else 160
            x = geo.x() + (geo.width() - w) // 2
            y = geo.y() + (geo.height() - h) // 2
            self.position = QPoint(x, y)

    def set_status(self, text: str):
        """Updates the status text property in Splash.qml and flushes GUI events."""
        root = self.root_object()
        if root:
            root.set_property("statusText", text)
        QApplication.process_events()

    def finish(self, window=None):
        """Closes the splash window safely on the main thread after first frame."""
        def close_safely():
            if self._closed:
                return
            self._closed = True
            self.close()
            if window is not None and hasattr(window, "request_activate"):
                window.request_activate()

        frame_signal = getattr(window, "frameSwapped", None) or getattr(window, "frame_swapped", None)
        if window is not None and frame_signal is not None:
            def on_frame():
                try:
                    frame_signal.disconnect(on_frame)
                except Exception:
                    pass
                QTimer.single_shot(0, close_safely)

            frame_signal.connect(on_frame, Qt.ConnectionType.QueuedConnection)
            QTimer.single_shot(3000, close_safely)
        else:
            close_safely()
