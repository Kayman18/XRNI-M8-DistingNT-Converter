@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py xrni_to_m8_gui.py) else (python xrni_to_m8_gui.py)
if errorlevel 1 pause
