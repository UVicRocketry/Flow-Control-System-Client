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

# Bundle default configuration templates for standalone packages
config_dir = REPO_ROOT / "contents" / "config"
if config_dir.exists():
    datas.append((str(config_dir), "contents/config"))

# If metadata.json exists, bundle it
metadata_file = REPO_ROOT / "metadata.json"
if metadata_file.exists():
    datas.append((str(metadata_file), "."))

binaries = []

# Attempt to locate and bundle Kirigami & KDE QML modules so client runs portably anywhere
qml_search_roots = [
    Path("/usr/lib/x86_64-linux-gnu/qt6/qml"),
    Path("/usr/lib/qt6/qml"),
    Path("/usr/lib64/qt6/qml"),
]

# Windows KDE Craft search roots
if sys.platform == "win32":
    craft_root = Path(os.environ.get("CRAFT_ROOT", r"C:\CraftRoot"))
    for qml_sub in ["qml", r"bin\qml", r"lib\qml", r"share\qt6\qml", r"bin\data\qml", r"share\qml"]:
        cand = craft_root / qml_sub
        if cand.exists() and cand not in qml_search_roots:
            qml_search_roots.append(cand)

try:
    from PySide6.QtCore import QLibraryInfo
    pyside_qml = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    if pyside_qml.exists():
        qml_search_roots.insert(0, pyside_qml)
except Exception:
    pass

collected_kde_mods = set()
for root in qml_search_roots:
    org_kde = root / "org" / "kde"
    if org_kde.exists():
        for mod_path in org_kde.iterdir():
            if mod_path.is_dir() and mod_path.name not in collected_kde_mods:
                collected_kde_mods.add(mod_path.name)
                datas.append((str(mod_path), f"org/kde/{mod_path.name}"))
                # Also collect any shared libraries inside this QML module into binaries (.so on Linux, .dll on Windows)
                for lib_file in list(mod_path.rglob("*.so*")) + list(mod_path.rglob("*.dll")):
                    try:
                        rel_dir = lib_file.parent.relative_to(root)
                        binaries.append((str(lib_file.resolve()), str(rel_dir)))
                        if lib_file.is_symlink():
                            binaries.append((str(lib_file), str(rel_dir)))
                    except Exception:
                        pass

# Linux: collect Kirigami, KDE and Breeze shared libraries
lib_dirs = [
    Path("/usr/lib/x86_64-linux-gnu"),
    Path("/usr/lib"),
    Path("/usr/lib64"),
]
added_binaries = set()
for l_dir in lib_dirs:
    if l_dir.exists():
        for pattern in ["*Kirigami*.so*", "*KF6*.so*", "*Breeze*.so*", "*qqc2*.so*"]:
            for match in l_dir.glob(pattern):
                try:
                    resolved = match.resolve()
                    if resolved.is_file() and str(resolved) not in added_binaries:
                        added_binaries.add(str(resolved))
                        binaries.append((str(resolved), "."))
                        if match.name != resolved.name:
                            binaries.append((str(match), "."))
                except Exception:
                    pass

# Windows: collect dependent DLLs and Breeze icons from Craft
if sys.platform == "win32":
    craft_root = Path(os.environ.get("CRAFT_ROOT", r"C:\CraftRoot"))
    craft_bin = craft_root / "bin"
    if craft_bin.exists():
        for dll in craft_bin.glob("*.dll"):
            dll_lower = dll.name.lower()
            # Avoid conflicting with PySide6's Qt6 / python runtime dlls
            if not dll_lower.startswith("python") and not dll_lower.startswith("qt6"):
                binaries.append((str(dll), "."))
    for icon_sub in [r"bin\data\icons", r"share\icons"]:
        cand_icons = craft_root / icon_sub
        if cand_icons.exists():
            datas.append((str(cand_icons), "icons"))

# Hidden imports
hidden_imports = [
    "__feature__",
    "shiboken6",
    "backend",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickLayouts",
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

hidden_imports += collect_submodules("PySide6.QtQuickControls2")
hidden_imports += collect_submodules("PySide6.QtQuick")
hidden_imports += collect_submodules("PySide6.QtQml")

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
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

# Strip host-provided libraries that cause fontconfig XML schema/attribute warnings on modern Linux distributions
if sys.platform != "win32" and sys.platform != "darwin":
    EXCLUDED_HOST_LIBS = [
        "libfontconfig.so",
        "libfreetype.so",
    ]
    a.binaries = [
        item for item in a.binaries
        if not any(ex in item[0] for ex in EXCLUDED_HOST_LIBS)
    ]

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
