@echo off
cd /d "%~dp0"

echo === Usage Monitor Build ===

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

.venv\Scripts\pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    .venv\Scripts\pip install pyinstaller
)

REM VERSIONファイルからバージョンを読み込む
set /p VERSION=<VERSION
echo Version: %VERSION%

echo Generating icon...
.venv\Scripts\python scripts\gen_icon.py

echo Building EXE...
.venv\Scripts\pyinstaller ^
    --onefile ^
    -w ^
    --name "Usage_Monitor_v%VERSION%" ^
    --icon build_icon.ico ^
    --add-data "assets;assets" ^
    --add-data "VERSION;." ^
    --hidden-import pystray._win32 ^
    --exclude-module unittest ^
    --exclude-module test ^
    --exclude-module pip ^
    --exclude-module xml.sax ^
    --exclude-module xmlrpc ^
    --exclude-module sqlite3 ^
    --exclude-module multiprocessing ^
    --exclude-module concurrent ^
    --exclude-module asyncio ^
    --exclude-module lib2to3 ^
    --exclude-module pydoc ^
    --exclude-module doctest ^
    --exclude-module PIL._avif ^
    --exclude-module PIL._imagingft ^
    --exclude-module PIL._webp ^
    --exclude-module PIL._imagingcms ^
    --exclude-module PIL._imagingmorph ^
    --exclude-module PIL._imagingmath ^
    --exclude-module PIL.ImageFont ^
    --exclude-module PIL.ImageDraw ^
    --exclude-module PIL.WebPImagePlugin ^
    --exclude-module PIL.AvifImagePlugin ^
    --exclude-module setuptools ^
    --exclude-module pkg_resources ^
    --exclude-module _distutils_hack ^
    --exclude-module distutils ^
    --clean ^
    -y ^
    src\main.py

if exist "dist\Usage_Monitor_v%VERSION%.exe" (
    echo.
    echo Build OK: dist\Usage_Monitor_v%VERSION%.exe
) else (
    echo.
    echo Build FAILED
    exit /b 1
)
