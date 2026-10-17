# Flow Control System Client

PySide6 / Kirigami Client for the Flow Control System

## Running the client

Grab the newest release from Github's Releases tab!

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
  sudo apt update && sudo apt install -y \
    python3-pip \
    libgl1-mesa-dev libxkbcommon-x11-0 libegl1-mesa \
    libfontconfig1 libdbus-1-3 libxcb-cursor0 \
    qml6-module-org-kde-kirigami \
    qml6-module-qtquick-controls \
    qml6-module-qtquick-layouts \
    qt6-wayland \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good
  ```
  
- **Arch Linux**:
  ```sh
  sudo pacman -S python python-pyside6 kirigami qt6-declarative qt6-quickcontrols2 qt6-svg qt6-multimedia qt6-wayland qt6-websockets
  ```  

- **Fedora**:
  ```sh
  sudo dnf install \
    python3-pyside6 \
    kf6-kirigami \
    qt6-qtdeclarative \
    qt6-qtquickcontrols2 \
    qt6-qtsvg \
    qt6-qtmultimedia \
    qt6-qtwayland
  ```
  
- **Windows**

   To run or develop natively on Windows, install Kirigami and the KDE desktop style via **KDE Craft** as outlined in their [developer docs](https://develop.kde.org/docs/getting-started/kirigami/platforms-windows/):

   ```powershell
   # 1. Install KDE Craft
   iex ((new-object net.webclient).DownloadString('https://invent.kde.org/packaging/craft/-/raw/master/setup/install_craft.ps1'))

   # 2. In your Craft environment, install Kirigami and desktop styling
   craft kirigami kcoreaddons ki18n breeze breeze-icons kiconthemes qqc2-desktop-style
   ```
   
#### 2. Python packages
Install via `pip`:
```sh
pip install -r requirements.txt
```

## Automated builder

Standalone portable binaries for **Linux**, **Windows**, and **macOS** are built via **GitHub Actions**:

### Grabbing releases

1. Every push to `master`/`main` or pull request automatically triggers [.github/workflows/build.yml](.github/workflows/build.yml).
2. Built packages for all three operating systems are downloadable from the **Actions** tab → select the latest workflow run → **Artifacts**.
3. Pushing a version tag automatically generates a GitHub Release with all binary packages attached:
   ```sh
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. Build configuration, icons, and metadata are maintained under [`packaging/`](packaging/).
