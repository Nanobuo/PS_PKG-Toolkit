@echo off
rem Build PS-PKG-Toolkit.exe (GUI) and pspkg.exe (riga di comando) in dist\
rem Richiede Python 3.10+ installato e nel PATH.
setlocal
python -m venv .venv || goto :error
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
pip install -r requirements.txt pyinstaller pillow || goto :error
set QT_QPA_PLATFORM=offscreen
python -m unittest discover -s tests || goto :error
set QT_QPA_PLATFORM=
pyinstaller --noconfirm --onefile --windowed --name PS-PKG-Toolkit --icon assets\ps-pkg-toolkit.png --exclude-module tkinter pkgfree_gui.py || goto :error
pyinstaller --noconfirm --onefile --console --name pspkg --icon assets\ps-pkg-toolkit.png --exclude-module PySide6 --exclude-module qfluentwidgets --exclude-module tkinter pkgfree_cli.py || goto :error
echo.
echo Fatto: dist\PS-PKG-Toolkit.exe e dist\pspkg.exe
exit /b 0
:error
echo Build fallita.
exit /b 1
