@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem EXE_NAME must match VERSION in shortcut_notifier.py
set EXE_NAME=Keycastr-1.4.0-beta

python make_icon.py
pyinstaller --noconfirm --clean --onefile --windowed --name ShortcutNotifier --icon icon.ico shortcut_notifier.py

echo.
if exist "dist\ShortcutNotifier.exe" (
    if exist "dist\%EXE_NAME%.exe" del "dist\%EXE_NAME%.exe"
    ren "dist\ShortcutNotifier.exe" "%EXE_NAME%.exe"
)
echo Build done: dist\%EXE_NAME%.exe
echo Share it with users who do not have Python installed.
pause
