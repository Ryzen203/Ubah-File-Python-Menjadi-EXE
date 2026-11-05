# PyCompiler Studio

**ID:** Ubah file Python (`.py`) menjadi `.exe` siap pakai dengan antarmuka modern. Mendukung Windows 7 (32/64-bit) sampai Windows 11.
**EN:** Turn Python (`.py`) files into ready-to-run `.exe` with a modern GUI. Supports Windows 7 (32/64-bit) through Windows 11.

![tests](https://github.com/USERNAME/PyCompiler-Studio/actions/workflows/tests.yml/badge.svg)

## Fitur / Features
- Deteksi otomatis library dari `import` (+ `requirements.txt`), dipasang ke *virtual environment* terisolasi.
- Pilih target 32/64-bit dan Windows terlama (7 / 8.1 / 10 / 11); PyInstaller dipilih otomatis sesuai versi Python.
- Semua Python di folder `Python` (di samping aplikasi) terdeteksi otomatis, plus Python yang terpasang di PC.
- Ekstrak installer python.org yang sudah Anda punya tanpa memasangnya ke Windows (tanpa internet).
- Informasi file EXE (Properties › Details) dan *Date created*.
- Opsi: satu file / satu folder, tanpa konsol, mode latar belakang, hak admin, tanpa UPX, proses berhenti total saat ditutup.
- UI dua bahasa (Indonesia / English), mode gelap/terang.

## Menjalankan / Run
```
pip install -r requirements.txt
python pycompiler_studio.py
```
Atau klik dua kali `PyCompiler Studio.pyw` (tanpa jendela konsol). Butuh Python 3.8+ dan Windows.
Or double-click `PyCompiler Studio.pyw` (no console window). Requires Python 3.8+ and Windows.

## Membuat EXE aplikasi ini / Build this app as an EXE
```
build.bat
```
Hasil: `dist\PyCompiler Studio.exe`. Letakkan folder `Python` **di samping** EXE tersebut.
Output: `dist\PyCompiler Studio.exe`. Keep the `Python` folder **next to** the EXE.

## Kompatibilitas target / How target compatibility works

| Oldest Windows | Python needed | PyInstaller |
|---|---|---|
| Windows 7 | 3.8 (x86 or x64) | 5.13.2 |
| Windows 8.1 | 3.8 – 3.12 | latest |
| Windows 10 / 11 | 3.8+ | latest |

PyInstaller tidak bisa lintas-kompilasi, jadi sediakan versi Python yang dibutuhkan di folder `Python`
(mis. Python 3.8 **32-bit** untuk jangkauan terluas: satu EXE 32-bit jalan di Windows 32-bit dan 64-bit).
PyInstaller cannot cross-compile, so provide the Python versions you need in the `Python` folder
(e.g. Python 3.8 **32-bit** for the widest reach).

## Privasi sebelum publish / Privacy before publishing
```
python tools/check_privacy.py --term "NamaAnda"
python tools/check_privacy.py "dist/PyCompiler Studio.exe"
```
Memeriksa nama pengguna Windows, path `C:\Users\<user>` dan kata lain yang Anda tentukan. `build.bat` menjalankannya otomatis pada EXE.
Checks for your Windows user name, `C:\Users\<user>` paths and any extra words you give. `build.bat` runs it on the EXE automatically.

Aplikasi tidak menyimpan lokasi build di dalam EXE: folder `Python` dihitung saat aplikasi dijalankan, dari lokasi EXE di PC pengguna.
Do not commit `dist/`, `build/` or the `Python/` folder (already in `.gitignore`); publish the EXE through GitHub Releases.

## Tes / Tests
```
python tests/test_logic.py
```
Tes logika berjalan tanpa GUI/Windows (komponen GUI di-*stub*). / The logic tests need no GUI or Windows.

## Catatan / Notes
- Beberapa library tidak lagi menyediakan wheel untuk Python 3.8 / 32-bit; pip memilih versi terbaru yang kompatibel atau melewatinya dengan peringatan.
- Antivirus kadang menandai EXE satu-file (false positive umum PyInstaller).
- Data aplikasi disimpan di `~/.pycompiler_studio` (config, log, venv, folder kerja).

## Lisensi / License
MIT — lihat [LICENSE](LICENSE).
