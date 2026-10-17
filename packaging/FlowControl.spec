# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for Flow Control System Client
Multi-platform build spec for GitHub Actions CI/CD workflows.
Supports Linux (AppImage / Onedir), Windows (Portable .exe / Onedir), and macOS (.app bundle).
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

SPEC_ROOT = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_ROOT.parent

# Determine appropriate platform icon
if sys.platform == "win32":
    ICON_PATH = SPEC_ROOT / "icon.ico"
elif sys.platform == "darwin":
    ICON_PATH = SPEC_ROOT / "icon.icns"
else:
    ICON_PATH = SPEC_ROOT / "icon.png"

# Collect data files
datas = [
    (str(REPO_ROOT / "contents" / "qml"), "contents/qml"),
    (str(REPO_ROOT / "contents" / "qmldir"), "contents"),
]

# If metadata.json exists, bundle it
metadata_file = REPO_ROOT / "metadata.json"
if metadata_file.exists():
    datas.append((str(metadata_file), "."))

# Attempt to locate and bundle Kirigami QML modules so client runs portably anywhere
kirigami_candidates = [
    Path("/usr/lib/qt6/qml/org/kde/kirigami"),
    Path("/usr/lib64/qt6/qml/org/kde/kirigami"),
]

try:
    from PySide6.QtCore import QLibraryInfo
    qml_sys_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    kirigami_candidates.insert(0, qml_sys_path / "org" / "kde" / "kirigami")
except Exception:
    pass

for k_path in kirigami_candidates:
    if k_path.exists():
        datas.append((str(k_path), "org/kde/kirigami"))
        break

# Hidden imports
hidden_imports = [
    "__feature__",
    "backend",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

hidden_imports += collect_submodules("PySide6.QtQuickControls2")

excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "numpy",
    "test",
    "unittest",
]

a = Analysis(
    [str(REPO_ROOT / "contents" / "code" / "main.py")],
    pathex=[
        str(REPO_ROOT / "contents" / "code"),
        str(REPO_ROOT / "contents"),
        str(REPO_ROOT),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Standalone single-file executable (Windows Portable .exe and Linux standalone)
exe_single = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FlowControl-Portable",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
)

# Onedir distribution (Used for Linux AppDir and macOS .app bundle)
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FlowControl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
)

coll = COLLECT(
    exe_dir,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FlowControl",
)

# macOS Application Bundle (.app)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Flow Control.app",
        icon=str(ICON_PATH) if ICON_PATH.exists() else None,
        bundle_identifier="org.uvicrocketry.flowcontrol",
        info_plist={
            "CFBundleName": "Flow Control",
            "CFBundleDisplayName": "Flow Control System Client",
            "CFBundleExecutable": "FlowControl",
            "CFBundleIdentifier": "org.uvicrocketry.flowcontrol",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
        },
    )
