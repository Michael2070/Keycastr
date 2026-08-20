@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 版本号需要与 shortcut_notifier.py 中的 VERSION 保持一致
set EXE_NAME=Keycastr-1.3.3-beta

python make_icon.py
pyinstaller --noconfirm --clean --onefile --windowed --name ShortcutNotifier --icon icon.ico shortcut_notifier.py

echo.
if exist "dist\ShortcutNotifier.exe" (
    if exist "dist\%EXE_NAME%.exe" del "dist\%EXE_NAME%.exe"
    ren "dist\ShortcutNotifier.exe" "%EXE_NAME%.exe"
)
echo 打包完成：dist\%EXE_NAME%.exe
echo 可直接复制给没有 Python 环境的用户使用。
pause
