#!/usr/bin/env bash
# Build dist/PS-PKG-Toolkit-x86_64.AppImage. Needs: Python deps + pyinstaller installed, curl.
set -euo pipefail
cd "$(dirname "$0")/../.."

APPIMAGETOOL_VERSION=1.9.1
TOOL="build/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage"

pyinstaller --noconfirm --onedir --name PS-PKG-Toolkit --icon assets/ps-pkg-toolkit.png \
    --exclude-module tkinter pkgfree_main.py

rm -rf build/AppDir
mkdir -p build/AppDir/usr/bin
cp -a dist/PS-PKG-Toolkit build/AppDir/usr/bin/PS-PKG-Toolkit
cp packaging/linux/AppRun build/AppDir/AppRun
cp packaging/linux/ps-pkg-toolkit.desktop build/AppDir/ps-pkg-toolkit.desktop
cp assets/ps-pkg-toolkit.png build/AppDir/ps-pkg-toolkit.png
ln -sf ps-pkg-toolkit.png build/AppDir/.DirIcon

if [ ! -x "$TOOL" ]; then
    mkdir -p build
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL"
fi
# Extract-and-run: CI runners have no FUSE.
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" build/AppDir dist/PS-PKG-Toolkit-x86_64.AppImage
echo "Creato dist/PS-PKG-Toolkit-x86_64.AppImage"
