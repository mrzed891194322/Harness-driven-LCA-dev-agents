@echo off
REM One-click environment setup for the LCA Agent project.
REM Double-click this file to run uv sync and check/create .env.

setlocal
cd /d "%~dp0"

echo.
echo LCA Agent - Environment Setup
echo.

REM Check uv is available
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] uv not found in PATH. Please install uv first.
    echo         https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

REM Run the Python setup script via uv
uv run python scripts\setup_env\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Setup failed] Exit code: %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
endlocal