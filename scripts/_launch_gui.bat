@echo off
REM One-click launcher for the LCA Agent Gradio GUI.
REM Double-click this file to run scripts\gui_control\launch_gui.ps1 via PowerShell.
REM Closing this window or pressing Ctrl+C will terminate the gradio process tree
REM automatically (via Windows Job Object).

setlocal
cd /d "%~dp0.."

REM Launch PowerShell with ExecutionPolicy Bypass to avoid execution policy issues
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gui_control\launch_gui.ps1"

REM On failure, keep the window open so the error can be read
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Launch failed] Exit code: %ERRORLEVEL%
    pause
)

endlocal