@echo off
rem Baut den TW1 PAR Editor als eine Exe (PyInstaller, onefile, ohne Konsole).
rem Ergebnis: %~dp0dist\TW1 PAR Editor.exe - danach auf den Desktop kopieren.
setlocal
pushd "%~dp0"
"C:\Users\marco\AppData\Local\Programs\Python\Python313\python.exe" -m PyInstaller --noconfirm --onefile --windowed ^
  --name "TW1 PAR Editor" --icon "%~dp0par_editor.ico" ^
  --add-data "%~dp0par_editor.ico;." --add-data "%~dp0tw1_sdk_fields.json;." ^
  --add-data "%~dp0tw1_sdk_labels.json;." --add-data "%~dp0tw1_sdk_descriptions.json;." ^
  --hidden-import theme ^
  --distpath "%~dp0dist" --workpath "%TEMP%\par_editor_build" --specpath "%TEMP%\par_editor_build" tw1_par_editor.py
set rc=%errorlevel%
popd
if %rc% neq 0 (echo BUILD FEHLGESCHLAGEN & exit /b %rc%)
echo BUILD OK: %~dp0dist\TW1 PAR Editor.exe
