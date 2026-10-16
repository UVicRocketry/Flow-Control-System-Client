# This Python file uses the following encoding: utf-8
"""
Flow Control Client - Backend Controller
Provides QObject bridge between PySide6/QML and native QWebSocket.
Currently a stub
"""

from PySide6 import QtCore


class Backend(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def connect(self):
        pass
