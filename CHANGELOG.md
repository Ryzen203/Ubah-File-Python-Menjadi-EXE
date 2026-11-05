# Changelog

## Repository
- Added `tools/check_privacy.py` (scans source/EXE for user name and absolute user paths); `build.bat` runs it automatically.
- Removed a personal sample path from the tests.

## 1.6.5
- Optional "deep clean" (`--clean`) separated from the work-folder clean; PyInstaller's shared cache is untouched by default.
- Build result is verified: the EXE must exist and not be empty.
- App-name validation (Windows reserved names/characters) and absolute output folder.
- Libraries are only installed after confirmation, and only those missing in the build venv.

## 1.6.0 – 1.6.4
- Fixed `Python` folder next to the app; PC-installed Pythons listed first, highest version first.
- Extract python.org installers locally (never installs into Windows).
- "File information" card (version resource + Date created).
- One build venv per `python.exe`; no needless re-downloads.
