@echo off
rem Baut den TW1 PAR Editor als eine Exe (PyInstaller, onefile, ohne Konsole).
rem Ergebnis: %~dp0dist\TW1 PAR Editor.exe - danach auf den Desktop kopieren.
setlocal
pushd "%~dp0"
py -3.13 -m PyInstaller --noconfirm --onefile --windowed ^
  --name "TW1_PAR_Editor" --icon "%~dp0par_editor.ico" ^
  --add-data "%~dp0par_editor.ico;." --add-data "%~dp0tw1_sdk_fields.json;." ^
  --add-data "%~dp0tw1_sdk_labels.json;." --add-data "%~dp0tw1_sdk_descriptions.json;." ^
  --add-data "%~dp0untested.json;." ^
  --hidden-import theme --hidden-import guidebook --hidden-import updater --hidden-import version --hidden-import categories ^
  --hidden-import bulktools --hidden-import bulkui --hidden-import dropfiles ^
  --hidden-import foxfeedback --hidden-import foxfeedback_ui ^
  --distpath "%~dp0dist" --workpath "%TEMP%\par_editor_build" --specpath "%TEMP%\par_editor_build" tw1_par_editor.py
set rc=%errorlevel%
popd
if %rc% neq 0 (echo BUILD FEHLGESCHLAGEN & exit /b %rc%)
echo BUILD OK: %~dp0dist\TW1 PAR Editor.exe
