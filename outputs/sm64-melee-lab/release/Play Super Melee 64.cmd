@echo off
if exist "%~dp0Super Melee 64.exe" (
  start "" "%~dp0Super Melee 64.exe"
  exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Super Melee 64\SuperMelee64.exe" (
  start "" "%LOCALAPPDATA%\Programs\Super Melee 64\SuperMelee64.exe"
  exit /b 0
)
call "%~dp0Setup Windows.cmd"
