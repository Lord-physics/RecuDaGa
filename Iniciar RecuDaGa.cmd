@echo off
cd /d "%~dp0"
py -3 -m RecuDaGa
if errorlevel 1 pause
