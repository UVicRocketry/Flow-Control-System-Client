# Flow Control System Client

PySide6 / Kirigami Client for the Flow Control System

## Running the client

Grab the newest release from Github's [releases](https://github.com/UVicRocketry/Flow-Control-System-Client/releases) tab!

## Development

Run directly from source:
```sh
python contents/code/main.py
```

### Runtime dependencies

When running or developing from source, the following dependencies are required:

#### 1. System libraries & QML modules

The UI utilizes KDE's **Kirigami** framework (`org.kde.kirigami`) and Qt Quick Controls:

- **Ubuntu / Debian / WSL**:
  ```sh
  sudo apt-get install -y \
    python3 python3-pip \
    qml6-module-org-kde-kirigami \
    qml6-module-org-kde-qqc2desktopstyle \
    qml6-module-qtquick-controls \
    qml6-module-qtquick-layouts \
    qml6-module-qtquick-templates \
    qml6-module-qtquick-shapes \
    qml6-module-qtwebsockets \
    qml6-module-qtmultimedia \
    libqt6multimedia6 \
    qt6-wayland
  ```

- **Arch Linux**:
  ```sh
  sudo pacman -S --needed \
    python \
    pyside6 \
    kirigami \
    qqc2-desktop-style \
    kiconthemes \
    kcoreaddons \
    ki18n \
    qt6-base \
    qt6-declarative \
    qt6-svg \
    qt6-wayland \
    qt6-websockets \
    qt6-multimedia \
    qt6-multimedia-ffmpeg \
    qt6-shadertools
  ```

- **Fedora**:
  ```sh
  sudo dnf install \
    python3-pyside6 \
    kf6-kirigami \
    kf6-qqc2-desktop-style \
    kf6-kiconthemes \
    kf6-kcoreaddons \
    kf6-ki18n \
    qt6-qtdeclarative \
    qt6-qtsvg \
    qt6-qtwayland \
    qt6-qtwebsockets \
    qt6-qtmultimedia \
    qt6-qtshadertools
  ```

- **Windows (MSYS2 UCRT64)**:

  Install [MSYS2](https://www.msys2.org/) and open the **MSYS2 UCRT64** shell, then install the required packages:

  ```sh
  pacman -S --needed \
    mingw-w64-ucrt-x86_64-python \
    mingw-w64-ucrt-x86_64-python-pip \
    mingw-w64-ucrt-x86_64-pyside6 \
    mingw-w64-ucrt-x86_64-kirigami \
    mingw-w64-ucrt-x86_64-qqc2-desktop-style \
    mingw-w64-ucrt-x86_64-breeze \
    mingw-w64-ucrt-x86_64-breeze-icons \
    mingw-w64-ucrt-x86_64-kcoreaddons \
    mingw-w64-ucrt-x86_64-ki18n \
    mingw-w64-ucrt-x86_64-kiconthemes \
    mingw-w64-ucrt-x86_64-qt6-websockets \
    mingw-w64-ucrt-x86_64-qt6-multimedia
  ```

  Run the client from the same **MSYS2 UCRT64** shell (`python contents/code/main.py`). To build the Windows package locally, also install `mingw-w64-ucrt-x86_64-pyinstaller` and `mingw-w64-ucrt-x86_64-python-pillow`.

#### 2. Python packages
If you are not using your system or MSYS2 `pyside6` package (e.g., on Ubuntu/Debian or inside a standalone virtualenv), install via `pip`:
```sh
pip install -r requirements.txt
```

## Automated builder

Standalone portable binaries for **Linux**, **Windows**, and **macOS (not currently shipping)** are built via **GitHub Actions**:

### Grabbing releases

1. Every push to `master`/`main` or pull request automatically triggers [.github/workflows/build.yml](.github/workflows/build.yml).
2. Built packages for all three operating systems are downloadable from the **Actions** tab → select the latest workflow run → **Artifacts**.
3. Pushing a version tag automatically generates a GitHub Release with all binary packages attached:
   ```sh
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. Build configuration, icons, and metadata are maintained under [`packaging/`](packaging/).
