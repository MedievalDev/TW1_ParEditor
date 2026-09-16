@echo off
rem Startet die gebaute Exe im Selbsttest-Modus und zeigt die Zeile (PY_TOOL_DESIGN.md 7.6).
set "PAR_EDITOR_SELFTEST=%TEMP%\par_editor_selftest.txt"
del "%PAR_EDITOR_SELFTEST%" 2>nul
start "" /wait "%~dp0dist\TW1_PAR_Editor.exe"
timeout /t 3 >nul
type "%PAR_EDITOR_SELFTEST%"
