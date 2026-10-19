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
    (str(REPO_ROOT / "contents" / "qmldir"), "contents"),
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

# Collect QtWebSockets QML module
collected_extra_mods = set()
for root in qml_search_roots:
    for mod_name in ["QtWebSockets"]:
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
            for pattern in ["*Kirigami*.so*", "*KF6*.so*", "*Breeze*.so*", "*qqc2*.so*", "*WebSockets*.so*"]:
                for match in l_dir.glob(pattern):
                    add_binary_once(match, ".")
            for plugin in l_dir.rglob("*KIconEnginePlugin*.so*"):
                add_binary_once(plugin, "PySide6/Qt/plugins/iconengines")
            # Bundle Kirigami platform theme plugins (org.kde.desktop.so)
            for kf6_plat in l_dir.rglob("kf6/kirigami/platform/*.so*"):
                add_binary_once(kf6_plat, "PySide6/Qt/plugins/kf6/kirigami/platform")

# Windows & macOS Craft shared libraries, KIconEnginePlugin, and Breeze Icons
if sys.platform in ("win32", "darwin") and craft_root.exists():
    # 1. Collect KF6, Kirigami, Breeze, WebSockets, and gettext/iconv runtime libraries
    lib_patterns = [
        "*KF6*",
        "*Kirigami*",
        "*Breeze*",
        "*qqc2*",
        "*WebSockets*",
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
]

hidden_imports += collect_submodules("PySide6.QtQuickControls2")
hidden_imports += collect_submodules("PySide6.QtQuick")
hidden_imports += collect_submodules("PySide6.QtQml")
hidden_imports += collect_submodules("PySide6.QtWebSockets")

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

# Strip host-provided libraries that cause fontconfig XML warnings on Linux
if sys.platform.startswith("linux"):
    EXCLUDED_HOST_LIBS = [
        "libfontconfig.so",
        "libfreetype.so",
    ]
    a.binaries = [
        item for item in a.binaries
        if not any(ex in item[0] for ex in EXCLUDED_HOST_LIBS)
    ]

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
