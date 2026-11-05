@echo off
setlocal
REM Build PyCompiler Studio itself into a single EXE (dist\PyCompiler Studio.exe).
REM Windows 7 users: run this with Python 3.8 and "pip install pyinstaller==5.13.2" first.
cd /d "%~dp0"

python -m pip install -r requirements-dev.txt || goto :fail
REM Relative script path + spec/work files inside "build\": no absolute path of this PC is passed on.
python -m PyInstaller --noconfirm --clean --onefile --noconsole --noupx ^
  --specpath build --workpath build\work ^
  --name "PyCompiler Studio" --collect-all customtkinter pycompiler_studio.py || goto :fail

REM Privacy check: the EXE must not contain your user name or user-profile path.
python tools\check_privacy.py "dist\PyCompiler Studio.exe" || goto :leak

echo.
echo Done: dist\PyCompiler Studio.exe
echo Keep the "Python" folder in the same folder as the EXE.
exit /b 0

:leak
echo.
echo PRIVACY WARNING: personal data was found (see above). Do NOT publish this EXE.
exit /b 2

:fail
echo.
echo Build failed. See the messages above.
exit /b 1
