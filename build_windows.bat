@echo off
REM Build Kenan's AutoClicker into a single Windows .exe
REM Just double-click this file on Windows.

python -m pip install --upgrade pip
python -m pip install pynput pyinstaller
python -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py

echo.
echo Done!  Your app:  dist\KenansAutoClicker.exe
pause
