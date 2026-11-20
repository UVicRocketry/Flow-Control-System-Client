# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for Flow Control System Client
Windows (MSYS2 UCRT64) onedir build spec for GitHub Actions CI/CD workflows.
(Linux AppImages are built separately with Arch Linux + Anylinux quick-sharun.)
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

SPEC_ROOT = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_ROOT.parent

# ============================================================================
# 1. ICON RESOLUTION & AUTO-GENERATION
# ============================================================================
PNG_ICON = SPEC_ROOT / "icon.png"
ICON_PATH = SPEC_ROOT / "icon.ico"
if not ICON_PATH.exists() and PNG_ICON.exists():
    try:
        from PIL import Image
        img = Image.open(PNG_ICON)
        img.save(ICON_PATH, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    except Exception as e:
        print(f"[Spec Warning] Could not auto-generate icon.ico via Pillow: {e}")

# ============================================================================
# 2. DATA FILES & ASSETS
# ============================================================================
datas = [
    (str(REPO_ROOT / "contents" / "qml"), "contents/qml"),
]

if PNG_ICON.exists():
    datas.append((str(PNG_ICON), "contents/qml/img"))

for rel_cfg in ("contents/config/config.json", "contents/config/graphs/graphs.json"):
    cfg_file = REPO_ROOT / rel_cfg
    if cfg_file.exists():
        datas.append((str(cfg_file), str(Path(rel_cfg).parent).replace("\\", "/")))

metadata_file = REPO_ROOT / "metadata.json"
if metadata_file.exists():
    datas.append((str(metadata_file), "."))

icons_dir = REPO_ROOT / "contents" / "icons"
if icons_dir.exists():
    datas.append((str(icons_dir), "contents/icons"))

binaries = []

# ============================================================================
# 3. QML MODULES (Kirigami, QQC2 Desktop Style, KDE Frameworks)
# ============================================================================
# In MSYS2 UCRT64, sys.prefix is `<msys64>/ucrt64`; CRAFT_ROOT may override it.
sys_root = Path(os.environ.get("CRAFT_ROOT", sys.prefix))
qml_search_roots = []

try:
    from PySide6.QtCore import QLibraryInfo
    pyside_qml = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    if pyside_qml.exists():
        qml_search_roots.append(pyside_qml)
except Exception:
    pass

if sys_root.exists():
    for qml_sub in ["share/qt6/qml", "qml", "bin/qml", "lib/qml", "share/qml"]:
        cand = sys_root / qml_sub
        if cand.exists() and cand not in qml_search_roots:
            qml_search_roots.append(cand)

collected_kde_mods = set()
for root in qml_search_roots:
    org_kde = root / "org" / "kde"
    if org_kde.exists():
        for mod_path in org_kde.iterdir():
            if mod_path.is_dir() and mod_path.name not in collected_kde_mods:
                collected_kde_mods.add(mod_path.name)
                datas.append((str(mod_path), f"org/kde/{mod_path.name}"))
                for lib_file in mod_path.rglob("*.dll"):
                    try:
                        rel_dir = lib_file.parent.relative_to(root)
                        binaries.append((str(lib_file.resolve()), str(rel_dir)))
                    except Exception:
                        pass

# sanity check
if "kirigami" not in collected_kde_mods:
    raise RuntimeError(
        f"CRITICAL: 'org/kde/kirigami' was not found in any QML search path: {qml_search_roots}"
    )

# Collect QtWebSockets, QtQuick/Shapes, and QtMultimedia QML modules
collected_extra_mods = set()
for root in qml_search_roots:
    for mod_name in ["QtWebSockets", "QtQuick/Shapes", "QtMultimedia"]:
        cand_mod = root / mod_name
        if cand_mod.exists() and mod_name not in collected_extra_mods:
            collected_extra_mods.add(mod_name)
            datas.append((str(cand_mod), mod_name))
            for lib_file in cand_mod.rglob("*.dll"):
                try:
                    rel_dir = lib_file.parent.relative_to(root)
                    binaries.append((str(lib_file.resolve()), str(rel_dir)))
                except Exception:
                    pass

# ============================================================================
# 4. SHARED LIBRARIES & BREEZE ICON ENGINE (MSYS2 UCRT64)
# ============================================================================
added_binaries = set()


def add_binary_once(src_path: Path, dest_dir: str = "."):
    try:
        resolved = src_path.resolve()
        if resolved.is_file() and str(resolved) not in added_binaries:
            added_binaries.add(str(resolved))
            binaries.append((str(resolved), dest_dir))
    except Exception:
        pass


if sys_root.exists():
    # 1. Collect KF6, Kirigami, Breeze, WebSockets, QuickShapes, Multimedia, and gettext/iconv runtime DLLs
    lib_patterns = [
        "*KF6*",
        "*Kirigami*",
        "*Breeze*",
        "*qqc2*",
        "*WebSockets*",
        "*QuickShapes*",
        "*Multimedia*",
        "*intl*",
        "*iconv*",
        "*pcre2*",
    ]
    for sub in ["bin", "lib"]:
        search_dir = sys_root / sub
        if search_dir.exists():
            for pat in lib_patterns:
                for lib in search_dir.glob(f"{pat}.dll"):
                    add_binary_once(lib, ".")

    # 2. Collect KIconEnginePlugin so QIcon::fromTheme("...") works on Windows
    for plugin in sys_root.rglob("*KIconEnginePlugin*.dll"):
        add_binary_once(plugin, "PySide6/Qt/plugins/iconengines")
        add_binary_once(plugin, "qt6_plugins/iconengines")

    # 3. Collect Breeze widget style plugin
    for style_plugin in sys_root.rglob("*breeze*.dll"):
        if "styles" in style_plugin.parts:
            add_binary_once(style_plugin, "PySide6/Qt/plugins/styles")

# ============================================================================
# 5. ANALYSIS & PACKAGING
# ============================================================================
hidden_imports = [
    "shiboken6",
    "actuator_controller",
    "backend",
    "camera_controller",
    "config_manager",
    "config_store",
    "log_manager",
    "numpy",
    "platformdirs",
    "splash",
    "telemetry_files",
    "telemetry_series",
    "telemetry_store",
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
    "PySide6.QtWebSockets",
    "PySide6.QtMultimedia",
]

hidden_imports += collect_submodules("PySide6.QtQuickControls2")
hidden_imports += collect_submodules("PySide6.QtQuick")
hidden_imports += collect_submodules("PySide6.QtQml")
hidden_imports += collect_submodules("PySide6.QtWebSockets")
hidden_imports += collect_submodules("PySide6.QtMultimedia")

excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
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

EXCLUDED_QT_TOKENS = (
    "qt3d",
    "qt63d",
    "qtcharts",
    "qt6charts",
    "qtdatavisualization",
    "qt6datavisualization",
    "qtquick3d",
    "qt6quick3d",
    "qtwebengine",
    "qt6webengine",
    "qtwebview",
    "qt6webview",
    "qtwebchannel",
    "qt6webchannel",
    "qtpdf",
    "qt6pdf",
    "qtvirtualkeyboard",
    "qt6virtualkeyboard",
    "qtsensors",
    "qt6sensors",
    "qtlocation",
    "qt6location",
    "qtpositioning",
    "qt6positioning",
    "qtbluetooth",
    "qt6bluetooth",
    "qtnfc",
    "qt6nfc",
    "qtserial",
    "qt6serial",
    "qtremoteobjects",
    "qt6remoteobjects",
    "qtscxml",
    "qt6scxml",
    "qtstatemachine",
    "qt6statemachine",
    "qttexttospeech",
    "qt6texttospeech",
    "qthttpserver",
    "qt6httpserver",
    "qtgrpc",
    "qt6grpc",
    "qtprotobuf",
    "qt6protobuf",
    "qtdesigner",
    "qt6designer",
    "qthelp",
    "qt6help",
    "qttest",
    "qt6test",
    "qtsql",
    "qt6sql",
    "qtxml",
    "qt6xml",
    "qtuitools",
    "qt6uitools",
)


def _keep_entry(dest_name: str) -> bool:
    norm = dest_name.replace("\\", "/").lower()
    if norm.startswith("contents/") or "fluentwinui3" in norm:
        return True
    return not any(tok in norm for tok in EXCLUDED_QT_TOKENS)


a.binaries = [entry for entry in a.binaries if _keep_entry(entry[0])]
a.datas = [entry for entry in a.datas if _keep_entry(entry[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Onedir distribution (packaged into FlowControl-Windows-Portable.zip)
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FlowControl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="FlowControl",
)
