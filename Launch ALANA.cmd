@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m src.app
) else (
    py -3 -m src.app
)

if errorlevel 1 (
    echo.
    echo ALANA could not start. Run: pip install -r requirements.txt
    pause
)
