# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for Flow Control System Client
Multi-platform build spec for GitHub Actions CI/CD workflows.
Supports Linux (AppImage / Onedir), Windows (Portable .exe & Onedir), and macOS (.app bundle).
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

SPEC_ROOT = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_ROOT.parent

# ============================================================================
# 1. PLATFORM ICON RESOLUTION & AUTO-GENERATION
# ============================================================================
PNG_ICON = SPEC_ROOT / "icon.png"
if sys.platform == "win32":
    ICON_PATH = SPEC_ROOT / "icon.ico"
    if not ICON_PATH.exists() and PNG_ICON.exists():
        try:
            from PIL import Image
            img = Image.open(PNG_ICON)
            img.save(ICON_PATH, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        except Exception as e:
            print(f"[Spec Warning] Could not auto-generate icon.ico via Pillow: {e}")
elif sys.platform == "darwin":
    ICON_PATH = SPEC_ROOT / "icon.icns"
    if not ICON_PATH.exists() and PNG_ICON.exists():
        try:
            from PIL import Image
            img = Image.open(PNG_ICON)
            img.save(ICON_PATH)
        except Exception as e:
            print(f"[Spec Warning] Could not auto-generate icon.icns via Pillow: {e}")
else:
    ICON_PATH = PNG_ICON

# ============================================================================
# 2. DATA FILES & ASSETS
# ============================================================================
datas = [
    (str(REPO_ROOT / "contents" / "qml"), "contents/qml"),
]

if PNG_ICON.exists():
    datas.append((str(PNG_ICON), "contents/qml/img"))

config_dir = REPO_ROOT / "contents" / "config"
if config_dir.exists():
    datas.append((str(config_dir), "contents/config"))

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
qml_search_roots = [
    Path("/usr/lib/x86_64-linux-gnu/qt6/qml"),
    Path("/usr/lib/qt6/qml"),
    Path("/usr/lib64/qt6/qml"),
]

# Locate KDE Craft or MSYS2 UCRT64 root on Windows and macOS
if sys.platform == "win32":
    # In MSYS2 UCRT64, sys.prefix is already `<msys64>/ucrt64`
    default_craft = sys.prefix if (Path(sys.prefix) / "share" / "qt6" / "qml").exists() else r"C:\CraftRoot"
else:
    default_craft = str(Path.home() / "CraftRoot")

craft_root = Path(os.environ.get("CRAFT_ROOT", default_craft))

if sys.platform in ("win32", "darwin") and craft_root.exists():
    for qml_sub in ["qml", "bin/qml", "lib/qml", "share/qt6/qml", "bin/data/qml", "share/qml"]:
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
                # Collect C++ QML plugin binaries (.so, .dll, .dylib)
                for ext in ("*.so*", "*.dll", "*.dylib"):
                    for lib_file in mod_path.rglob(ext):
                        try:
                            rel_dir = lib_file.parent.relative_to(root)
                            binaries.append((str(lib_file.resolve()), str(rel_dir)))
                            if lib_file.is_symlink():
                                binaries.append((str(lib_file), str(rel_dir)))
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
            for ext in ("*.so*", "*.dll", "*.dylib"):
                for lib_file in cand_mod.rglob(ext):
                    try:
                        rel_dir = lib_file.parent.relative_to(root)
                        binaries.append((str(lib_file.resolve()), str(rel_dir)))
                        if lib_file.is_symlink():
                            binaries.append((str(lib_file), str(rel_dir)))
                    except Exception:
                        pass

# ============================================================================
# 4. SHARED LIBRARIES & BREEZE ICON ENGINE (Linux, Windows, macOS)
# ============================================================================
added_binaries = set()


def add_binary_once(src_path: Path, dest_dir: str = "."):
    try:
        resolved = src_path.resolve()
        if resolved.is_file() and str(resolved) not in added_binaries:
            added_binaries.add(str(resolved))
            binaries.append((str(resolved), dest_dir))
            if src_path.name != resolved.name:
                binaries.append((str(src_path), dest_dir))
    except Exception:
        pass


# Linux shared libraries & icon plugins
if sys.platform.startswith("linux"):
    for l_dir in [Path("/usr/lib/x86_64-linux-gnu"), Path("/usr/lib"), Path("/usr/lib64")]:
        if l_dir.exists():
            for pattern in ["*Kirigami*.so*", "*KF6*.so*", "*Breeze*.so*", "*qqc2*.so*"]:
                for match in l_dir.glob(pattern):
                    add_binary_once(match, ".")
            # Bundle Kirigami platform theme plugins (org.kde.desktop.so)
            for kf6_plat in l_dir.rglob("kf6/kirigami/platform/*.so*"):
                add_binary_once(kf6_plat, "PySide6/Qt/plugins/kf6/kirigami/platform")
            # Bundle QtMultimedia FFmpeg backend plugin for hardware-decoded RTSP
            for mm_plug in l_dir.rglob("qt6/plugins/multimedia/*ffmpeg*.so*"):
                add_binary_once(mm_plug, "PySide6/Qt/plugins/multimedia")

# Windows & macOS Craft shared libraries, KIconEnginePlugin, and Breeze Icons
if sys.platform in ("win32", "darwin") and craft_root.exists():
    # 1. Collect KF6, Kirigami, Breeze, WebSockets, QuickShapes, and gettext/iconv runtime libraries
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
        search_dir = craft_root / sub
        if search_dir.exists():
            for pat in lib_patterns:
                for ext in (".dll", ".dylib"):
                    for lib in search_dir.glob(f"{pat}{ext}*"):
                        add_binary_once(lib, ".")

    # 2. Collect KIconEnginePlugin so QIcon::fromTheme("...") works on both MSYS2 and Craft
    for plugin in craft_root.rglob("*KIconEnginePlugin*"):
        if plugin.suffix in (".dll", ".dylib"):
            add_binary_once(plugin, "PySide6/Qt/plugins/iconengines")
            add_binary_once(plugin, "qt6_plugins/iconengines")

    for style_plugin in craft_root.rglob("*breeze*"):
        if "styles" in style_plugin.parts and style_plugin.suffix in (".dll", ".dylib"):
            add_binary_once(style_plugin, "PySide6/Qt/plugins/styles")

    # 3. Breeze icons: Minimal fallback icons are already bundled via contents/icons
    # rather than copying the entirety of Breeze icons (~100MB+).

# ============================================================================
# 5. ANALYSIS & PACKAGING
# ============================================================================
hidden_imports = [
    "__feature__",
    "shiboken6",
    "backend",
    "config_manager",
    "telemetry_files",
    "telemetry_series",
    "splash",
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

# Strip host-provided libraries and unused Qt/PySide6-Addons modules on Linux
if sys.platform.startswith("linux"):
    EXCLUDED_HOST_LIBS = [
        "libfontconfig.so",
        "libfreetype.so",
        "libGL.so",
        "libEGL.so",
        "libGLX.so",
        "libGLdispatch.so",
        "libdrm.so",
        "libglib-2.0.so",
        "libgobject-2.0.so",
        "libgio-2.0.so",
        "libgmodule-2.0.so",
        "libgthread-2.0.so",
        "libharfbuzz.so",
        "libmount.so",
        # Host GTK3 stack (used by host libqgtk3.so if loaded)
        "libgtk-3.so",
        "libgdk-3.so",
        "libcairo",
        "libpango",
        "libatk",
        "libatspi",
        "libepoxy.so",
        "libcolord.so",
        "libcloudproviders.so",
    ]

    EXCLUDED_PYSIDE_TOKENS = [
        # Unused PySide6-Addons modules (only QtWebSockets is needed)
        "Quick3D",
        "Qt63D",
        "Qt3D",
        "Charts",
        "Graphs",
        "Location",
        "Positioning",
        "SpatialAudio",
        "Qt6Pdf",
        "QtPdf",
        "Sensors",
        "VirtualKeyboard",
        "WebChannel",
        "RemoteObjects",
        "Scxml",
        "StateMachine",
        "TextToSpeech",
        "SerialPort",
        "SerialBus",
        "Bluetooth",
        "Qt6Nfc",
        "QtNfc",
        "HttpServer",
        "DataVisualization",
        "Qt5Compat",
        "QuickTimeline",
        "QuickEffectMaker",
        "WebView",
        "Qt6Coap",
        "Qt6Mqtt",
        "Qt6OpcUa",
        "Lottie",
        "Designer",
        "Qt6Help",
        "Qt6Sql",
        "Qt6Test",
        # Unused QtQuickControls2 styles on Linux (keep Basic + org.kde.desktop)
        "FluentWinUI3",
        "QuickControls2Imagine",
        "/Imagine/",
        "QuickControls2Material",
        "/Material/",
        "QuickControls2Universal",
        "/Universal/",
        "QuickControls2Fusion",
        "/Fusion/",
        "LabsStyleKit",
        "StyleKit",
        # Unused Qt translations
        "PySide6/Qt/translations/",
    ]

    def _keep_linux_entry(dest_path: str) -> bool:
        norm = dest_path.replace("\\", "/")
        if any(ex in norm for ex in EXCLUDED_HOST_LIBS):
            return False
        if norm.startswith("PySide6/") and any(tok in norm for tok in EXCLUDED_PYSIDE_TOKENS):
            return False
        return True

    a.binaries = [item for item in a.binaries if _keep_linux_entry(item[0])]
    a.datas = [item for item in a.datas if _keep_linux_entry(item[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Standalone single-file executable (Only built on Windows where it's uploaded)
if sys.platform == "win32":
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
        upx=False,
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

# Onedir distribution (Used for Linux AppDir, Windows ZIP, and macOS .app bundle)
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
