import os, sys, types, tempfile, threading, http.server, socketserver, json, pathlib, shutil, re
from unittest.mock import MagicMock

tmp = tempfile.mkdtemp()
os.environ["HOME"] = tmp; os.environ["USERPROFILE"] = tmp

# --- stubs: no tkinter / customtkinter in this container
tk = types.ModuleType("tkinter")
class Var:
    def __init__(self, value=None): self.v = value
    def get(self): return self.v
    def set(self, v): self.v = v
tk.StringVar = tk.BooleanVar = Var
tk.filedialog = MagicMock(); tk.messagebox = MagicMock(); tk.Tk = MagicMock
sys.modules["tkinter"] = tk
sys.modules["tkinter.filedialog"] = tk.filedialog; sys.modules["tkinter.messagebox"] = tk.messagebox
class FakeCTk(MagicMock):
    def _get_child_mock(self, **kw): return MagicMock()
ctk = MagicMock(); ctk.CTk = FakeCTk
sys.modules["customtkinter"] = ctk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pycompiler_studio as S
S.LAYOUT_POLL, S.LAYOUT_TIMEOUT = 0.01, 0.3   # keep the tests fast
S.PYTHON_DIR = pathlib.Path(tmp) / "AppFolder" / "Python"   # fixed folder next to the app (kept inside the temp dir)
P = pathlib.Path
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# ---------- pure helpers
S.hide_own_console(); ok(True, "hide_own_console is a no-op off Windows")

# ---------- scan + probe + discover with a fake folder tree (symlinks to this interpreter)
root = P(tmp) / "pythons"
for name in ("Python-3.8.10-32bit", "Python-3.12.10-64bit", "deep/er/Python-x"):
    d = root / name; d.mkdir(parents=True); (d / "python.exe").symlink_to(sys.executable)
venv = root / "myenv"; (venv / "Scripts").mkdir(parents=True); (venv / "pyvenv.cfg").write_text("x")
(venv / "Scripts" / "python.exe").symlink_to(sys.executable)
found = S.scan_dir_for_pythons(root)
ok(len(found) == 2 and not any("myenv" in f for f in found), f"scan finds 2 (depth<=2), skips venv and too-deep: {len(found)}")
extra = P(tmp) / "manual" / "python.exe"; extra.parent.mkdir(); extra.symlink_to(sys.executable)
infos = S.discover_pythons([str(root)], [str(extra), "/does/not/exist/python.exe"])
ok(len(infos) == 4, f"discover_pythons: 3 from folder (incl. the one 3 levels deep) + 1 manual, missing one ignored ({len(infos)})")
ok(S.discover_pythons([], []) == [], "discover_pythons itself is pure: nothing is found without roots/extras (system Pythons arrive as extras)")
i0 = infos[0]
ok(i0["ver"] == tuple(sys.version_info[:3]) and i0["bits"] == 64 and isinstance(i0["tk"], bool) and "pyi" in i0,
   f"probe returns ver/bits/tk/pyi -> tk={i0['tk']} pyi={i0['pyi']}")

# ---------- the app no longer downloads anything
ok(not any(hasattr(S, n) for n in ("download_file", "installer_url", "fetch_python_versions", "parse_version_index", "url_exists", "PY_FTP", "PYTHON_FALLBACK", "DOWNLOAD_DIR")), "download helpers are gone from the module")
ok(not any(hasattr(S.App, n) for n in ("t_download", "fetch_installer", "start_download", "start_refresh_versions", "t_versions", "apply_versions", "dl_bits")), "download methods are gone from App")
ok("urllib.request" not in P(S.__file__).read_text(encoding="utf-8"), "no network module is imported")

# ---------- App smoke test (UI = mocks; logic = real)
app = S.App()
ok(app.v_pyfolder.get() == str(S.PYTHON_DIR) and S.PYTHON_DIR.is_dir(), "fixed Python folder next to the app is shown and was created at start")
ok("v_pydir" not in vars(app) and "v_portable" not in vars(app), "the editable main/portable location fields are gone")
by = {n: next(i for i in infos if n in i["path"]) for n in ("Python-3.8.10-32bit", "Python-3.12.10-64bit", "manual")}
app.interps = [dict(by[n]) for n in ("Python-3.8.10-32bit", "Python-3.12.10-64bit", "manual")]
for i, (v, b) in zip(app.interps, [((3,8,10),32), ((3,12,10),64), ((3,12,4),64)]):
    i["ver"], i["bits"] = v, b
app.interps[0].update(tk=False, pyi=None); app.interps[1].update(tk=True, tkv="8.6.13", pyi="6.11.1")
app.v_arch.set("64-bit"); app.v_win.set("Windows 10"); app.refresh_target()
ok(app.sel["ver"] == (3,12,10), "auto picks highest compatible (3.12.10 64-bit)")
app.v_win.set("Windows 7"); app.v_arch.set("32-bit"); app.refresh_target()
ok(app.sel["ver"] == (3,8,10), "Windows 7 + 32-bit -> Python 3.8.10 32-bit")
app.v_arch.set("64-bit"); app.refresh_target()
ok(app.sel is None, "Windows 7 + 64-bit with only 3.12 64-bit -> no runtime")
# manual pick of an incompatible runtime
app.v_win.set("Windows 7"); app.v_runtime.set(app.interps[1]["path"]); app.update_selection()
ok(app.sel is None and app.target_runtime()["ver"] == (3,12,10), "manual incompatible: build blocked but install buttons still target it")
app.v_runtime.set("auto"); app.v_win.set("Windows 10")
# runtime list rendering uses ctk.CTkRadioButton/CTkLabel
ctk.CTkRadioButton.reset_mock(); ctk.CTkLabel.reset_mock()
app.refresh_target()
titles = [c.kwargs["text"] for c in ctk.CTkRadioButton.call_args_list]
labels = [c.kwargs.get("text", "") for c in ctk.CTkLabel.call_args_list]
ok(any("Python 3.12.10 · 64-bit" in t for t in titles) and any("3.8.10 · 32-bit" in t and "tidak cocok" in t for t in titles), f"runtime rows rendered: {titles}")
ok(any("PyInstaller: ✓ 6.11.1" in l for l in labels) and any("Tkinter: ✓ 8.6.13" in l for l in labels) and any("PyInstaller: ✗ tidak ada" in l for l in labels) and any("Tkinter: ✗ tidak ada" in l for l in labels), "badges show PyInstaller/Tkinter ✓/✗")
ok(any(l.startswith("Nama: Python-3.8.10-32bit") for l in labels), "name line shown")
ok("Terpasang di PC" in labels and "Di folder Python" in labels, "group headers shown: PC / Python folder")

# persistence of the file information card + version list (the Python folder is NOT stored: it is fixed)
app.v_fi["company"].set("ACME"); app.v_fi["version"].set("2.1"); app.v_fi_lang.set("English (en-US)")
app.v_fi["date"].set("2020-01-02"); app.v_fi_apply.set(False); app.save_cfg()
cfg = json.loads(S.CONFIG_FILE.read_text())
ok(cfg["fileinfo"]["company"] == "ACME" and cfg["fileinfo"]["version"] == "2.1" and cfg["fileinfo"]["apply_date"] is False
   and "date" not in cfg["fileinfo"] and "versions" not in cfg, "file information is persisted (date is per build); no download version list is stored")
ok("pydir" not in cfg and "portable" not in cfg and "extra" not in cfg, "no editable Python location is stored")
app2 = S.App()
ok(app2.v_fi["company"].get() == "ACME" and app2.v_fi_lang.get() == "English (en-US)" and app2.v_fi["date"].get() == "",
   "...and restored on next start")
S.CONFIG_FILE.write_text(json.dumps({"pydir": "C:/old", "portable": "C:/old2", "extra": ["x"], "fileinfo": {"lang": "bogus"}}))
app3 = S.App()
ok(app3.v_pyfolder.get() == str(S.PYTHON_DIR) and app3.v_fi_lang.get() == S.LANGUAGES[0][0] and app3.v_fi["version"].get() == "1.0.0.0", "old config keys are ignored; bad language falls back")

# tasks: capture commands instead of executing
cmds = []
def fake_run(cmd, cwd=None): cmds.append([str(c) for c in cmd]); return 0
app.run = fake_run
rt = app.interps[1]
ok(app.t_pyinstaller(rt, "pyinstaller==5.13.2") and cmds[-1][-3:] == ["install", "--upgrade", "pyinstaller==5.13.2"], "t_pyinstaller -> pip install --upgrade <spec>")
ok(S.pyinstaller_spec((3,7,9)) == "pyinstaller==5.13.2" and S.pyinstaller_spec((3,8,0)) == "pyinstaller==5.13.2", "PyInstaller spec: Python 3.7/3.8 -> 5.13.2")
ok(S.pyinstaller_spec((3,9,13)) == "pyinstaller" and S.pyinstaller_spec((3,14,0)) == "pyinstaller", "PyInstaller spec: Python 3.9+ -> latest")
# button: Windows 10 target + a 3.8 runtime selected must still pin 5.13.2
app.run = fake_run; app.v_win.set("Windows 10"); app.v_runtime.set("auto")
seen = []; app.start_task = lambda f, *a, **k: seen.append(a)
app.target_runtime = lambda: {"path": "py38", "ver": (3, 8, 0), "bits": 64}
app.start_install_pyi()
ok(seen and seen[0][1] == "pyinstaller==5.13.2", "button on Python 3.8 + Windows 10 target -> pins 5.13.2")
app.target_runtime = lambda: {"path": "py314", "ver": (3, 14, 10), "bits": 64}
seen.clear(); app.start_install_pyi()
ok(seen and seen[0][1] == "pyinstaller", "button on Python 3.14 -> latest")
del app.target_runtime
del app.start_task

# portable download = extraction only (no installer run, no registry/PATH)
def portable_run(cmd, cwd=None):
    cmd = [str(c) for c in cmd]; cmds.append(cmd)
    if "/layout" in cmd:
        d = P(cmd[cmd.index("/layout") + 1]) / "amd64"; d.mkdir(parents=True, exist_ok=True)   # MSIs in a sub-folder
        for n in ("core", "exe", "lib", "tcltk", "core_d", "tcltk_pdb"): (d / f"{n}.msi").write_text("x")   # ucrt.msi absent on purpose (optional)
        return 0
    if cmd[0] == "msiexec":
        name = P(cmd[2]).stem; T = P([a for a in cmd if a.startswith("TARGETDIR=")][0].split("=", 1)[1])
        files = {"core": ["python312.dll", "vcruntime140.dll", "DLLs/_ctypes.pyd"], "exe": ["python.exe", "pythonw.exe"],
                 "lib": ["Lib/os.py"], "tcltk": ["DLLs/_tkinter.pyd", "tcl/tcl8.6/init.tcl"]}[name]
        for f in files: (T / f).parent.mkdir(parents=True, exist_ok=True); (T / f).write_text("x")
        (T / f"{name}.msi").write_text("copy"); (T / f"{name}.cab").write_text("cab"); return 0
    if cmd[0].endswith("python.exe") and "ensurepip" in cmd:
        (P(cmd[0]).parent / "Lib/site-packages/pip").mkdir(parents=True, exist_ok=True); return 0
    raise AssertionError("unexpected command: " + " ".join(cmd))
app.run = portable_run; cmds.clear(); app.q.queue.clear()
pyz = P(tmp) / "pyz"; pyz.mkdir(); insts = P(tmp) / "insts"; insts.mkdir()
for nm in ("python-3.12.10.exe", "python-3.12.10-amd64.exe"): (insts / nm).write_bytes(b"MZ")
ok(app.t_local_installer(insts / "python-3.12.10.exe", pyz) is True and app.t_local_installer(insts / "python-3.12.10-amd64.exe", pyz) is True, "extracting 32-bit and 64-bit installers succeeds")
for b in (32, 64):
    d = pyz / f"Python-3.12.10-{b}bit"
    ok(all((d / f).is_file() for f in ("python.exe", "python312.dll", "vcruntime140.dll", "Lib/os.py", "DLLs/_tkinter.pyd", "tcl/tcl8.6/init.tcl")),
       f"{b}-bit folder has interpreter, DLLs, stdlib and Tcl/Tk")
    ok(not list(d.glob("*.msi")) and not list(d.glob("*.cab")), f"{b}-bit: no .msi/.cab left at root")
    ok((d / "Lib/site-packages/pip").is_dir(), f"{b}-bit: pip bootstrapped with ensurepip")
ok(all(c[0] == "msiexec" or "/layout" in c or "ensurepip" in c for c in cmds), "installer only ever used with /layout (never installs)")
ok(not any(a.startswith(("TargetDir=", "InstallAllUsers", "PrependPath")) for c in cmds for a in c), "no installer install flags used")
ok(not (S.HOME / "unpack").exists() or not any((S.HOME / "unpack").iterdir()), "temp unpack folders cleaned")
cmds.clear(); ok(app.t_local_installer(insts / "python-3.12.10.exe", pyz), "re-run -> 'already present'"); ok(not cmds, "no second extraction")
app.run = lambda cmd, cwd=None: 1
keep = P(tmp) / "pyz2" / "Python-3.9.13-64bit"; keep.mkdir(parents=True); (keep / "keep.txt").write_text("mine")
(insts / "python-3.9.13-amd64.exe").write_bytes(b"MZ"); (insts / "python-3.10.11.exe").write_bytes(b"MZ")
ok(app.t_local_installer(insts / "python-3.9.13-amd64.exe", P(tmp) / "pyz2") is False and (keep / "keep.txt").is_file(), "failure -> False, pre-existing folder untouched")
ok(app.t_local_installer(insts / "python-3.10.11.exe", P(tmp) / "pyz2") is False and not (P(tmp) / "pyz2" / "Python-3.10.11-32bit").exists(), "failure leaves no half-made folder")

# start_task: busy flag + queue round-trip
app.busy = False; app.q.queue.clear()
done = threading.Event(); app.start_task(lambda: done.set() or True)
done.wait(5)
import time; time.sleep(0.3)
ok(app.busy is True, "busy while task runs (build/task buttons disabled)")
app.poll()
ok(app.busy is False, "poll() 'task_done' re-enables UI")
app.start_task(lambda: 1/0); time.sleep(0.3); app.poll()
ok(app.busy is False and "ZeroDivisionError" in S.LOG_FILE.read_text(), "task exception handled (no crash)")
# UI: libraries entry removed, two folder pickers present, labels renamed
ctk.CTkLabel.reset_mock(); ctk.CTkEntry.reset_mock(); app.build_ui()
lbl = [c.kwargs.get("text", "") for c in ctk.CTkLabel.call_args_list]
ok("Folder Python (tetap)" in lbl and "Lokasi Python Utama" not in lbl and "Lokasi Python portable" not in lbl, "labels: one fixed 'Folder Python (tetap)', no editable locations")
ok("5. Informasi File" in lbl and "Versi aplikasi (mis. 1.0.0.0)" in lbl and "Tanggal dibuat (YYYY-MM-DD, kosong = hari ini)" in lbl and "Hak cipta (kosong = otomatis)" in lbl and "Komentar" in lbl, "file information card (5) is rendered")
ok(any(c.kwargs.get("text") == "Terapkan tanggal ke file EXE (Date created)" for c in ctk.CTkSwitch.call_args_list) and any(c.kwargs.get("text") == "Sertakan informasi file pada EXE" for c in ctk.CTkSwitch.call_args_list), "file information switches rendered")
ok(not any("Unduh" in c.kwargs.get("text", "") for c in ctk.CTkButton.call_args_list) and not any("Unduh Python" in l for l in lbl), "UI has no download button/section")
ok(any(c.kwargs.get("height") == 230 for c in ctk.CTkScrollableFrame.call_args_list), "runtime list lives in a fixed-height scrollable box")
ok(any(c.kwargs.get("state") == "disabled" and c.kwargs.get("textvariable") is app.v_pyfolder for c in ctk.CTkEntry.call_args_list), "Python folder entry is read-only")
ok(not any("Terdeteksi otomatis dari import" in l for l in lbl), "library hint removed")
ok(not any(c.kwargs.get("textvariable") is app.v_pkgs for c in ctk.CTkEntry.call_args_list), "library entry removed from UI")
# find_msi: sub-folders, ignores debug/pdb variants, root-level works too
fm = P(tmp) / "fm"; (fm / "amd64").mkdir(parents=True); (fm / "amd64" / "tcltk_d.msi").write_text("x")
ok(S.find_msi(fm, "tcltk") is None, "find_msi ignores tcltk_d.msi")
(fm / "amd64" / "tcltk.msi").write_text("x"); (fm / "core.msi").write_text("x")
ok(S.find_msi(fm, "tcltk").name == "tcltk.msi" and S.find_msi(fm, "core").parent == fm, "find_msi finds sub-folder and root-level MSIs")
ok("amd64" in S.list_tree(fm) and S.list_tree(P(tmp) / "nope").startswith("("), "list_tree diagnostic listing")

# ---------- local installer extraction (user already owns the installer)
ok(S.parse_installer_name("python-3.8.10.exe") == ("3.8.10", 32) and S.parse_installer_name("python-3.12.10-amd64.exe") == ("3.12.10", 64)
   and S.parse_installer_name("python-3.13.0rc1-amd64.exe") == ("3.13.0rc1", 64), "parse_installer_name 32/64-bit/prerelease")
ok(all(S.parse_installer_name(n) is None for n in ("setup.exe", "python-3.8.10.msi", "python-3.8.10-arm64.exe", "../python-3.8.10.exe")), "parse_installer_name rejects unknown names")
lbase = P(tmp) / "local_dest"; lbase.mkdir(); (lbase / "keep.txt").write_text("mine"); inst_dir = P(tmp) / "myinstallers"; inst_dir.mkdir()
inst = inst_dir / "python-3.12.10-amd64.exe"; inst.write_bytes(b"MZ-fake")
app.run = portable_run; cmds.clear()
ok(app.t_local_installer(inst, lbase) is True, "t_local_installer extracts a user-supplied installer")
d = lbase / "Python-3.12.10-64bit"
ok(all((d / f).is_file() for f in ("python.exe", "python312.dll", "Lib/os.py", "DLLs/_tkinter.pyd")) and (d / "Lib/site-packages/pip").is_dir(), "folder created in the chosen destination with pip")
ok(inst.is_file() and inst.read_bytes() == b"MZ-fake", "user's installer file is left untouched")
ok(d.parent == lbase, "default mode: always a Python-<ver>-<bits>bit sub-folder")
ok(all(c[0] == "msiexec" or "/layout" in c or "ensurepip" in c for c in cmds), "local installer only used with /layout")
cmds.clear(); ok(app.t_local_installer(inst, lbase) is True and not cmds, "re-run -> already present, nothing re-extracted")
ok(app.t_local_installer(inst_dir / "nope.exe", lbase) is False, "missing file -> False")
(inst_dir / "notes.txt").write_text("x"); ok(app.t_local_installer(inst_dir / "notes.txt", lbase) is False, "non-.exe -> False")
# bad signature: refused, file kept
S.verify_signature = lambda path: "HashMismatch"
bad = inst_dir / "python-3.9.13.exe"; bad.write_bytes(b"x")
ok(app.t_local_installer(bad, lbase) is False and bad.is_file() and not (lbase / "Python-3.9.13-32bit").exists(), "tampered installer refused and NOT deleted")
# renamed installer needs a Valid signature
S.verify_signature = lambda path: "NotSigned"
ren = inst_dir / "setup_my.exe"; ren.write_bytes(b"x")
ok(app.t_local_installer(ren, lbase) is False, "unknown name + not valid signature -> refused")
S.verify_signature = lambda path: "Valid"
ok(app.t_local_installer(ren, lbase) is True and (lbase / "Python-setup_my" / "python.exe").is_file(), "unknown name + valid signature -> extracted to Python-<name>")
S.verify_signature = lambda path: "Skipped"
# failure leaves no half-made folder
app.run = lambda cmd, cwd=None: 1
inst2 = inst_dir / "python-3.10.11.exe"; inst2.write_bytes(b"x")
ok(app.t_local_installer(inst2, lbase) is False and not (lbase / "Python-3.10.11-32bit").exists(), "extract failure leaves no half-made folder")
# UI button wiring
tk.filedialog.askopenfilename = MagicMock(return_value=str(inst)); tk.filedialog.askdirectory = MagicMock(return_value="/should/not/be/asked")
got = []; app.start_task = lambda f, *a, **k: got.append((f, a))
app.start_local_installer()
ok(got and got[0][0] == app.t_local_installer and got[0][1] == (os.path.normpath(str(inst)), str(S.PYTHON_DIR)), "button asks only for the installer; destination is the fixed Python folder")
ok(not tk.filedialog.askdirectory.called, "no destination dialog is shown any more")
got.clear(); tk.filedialog.askopenfilename = MagicMock(return_value=""); app.start_local_installer()
ok(not got, "cancelling the installer dialog starts nothing")
ep = P(tmp) / "fixed_empty"; ep.mkdir(); inst3 = inst_dir / "python-3.9.13.exe"; inst3.write_bytes(b"MZ")
S.verify_signature = lambda path: "Valid"; app.run = portable_run
ok(app.t_local_installer(inst3, ep) is True and (ep / "Python-3.9.13-32bit" / "python.exe").is_file() and not (ep / "python.exe").exists(), "even an EMPTY Python folder gets a Python-<ver>-<bits>bit sub-folder")
S.verify_signature = lambda path: "Skipped"
ctk.CTkLabel.reset_mock(); app.build_ui()
ok(any(c.kwargs.get("text") == "Sudah punya installer Python?" for c in ctk.CTkLabel.call_args_list) and any(c.kwargs.get("text") == "Ekstrak dari Installer…" for c in ctk.CTkButton.call_args_list), "new section rendered in the UI")

# ---------- direct bundle reading (installer is NOT run) + empty-folder target
def mkcab(size, inner=b""):
    body = b"MSCF" + bytes(4) + size.to_bytes(4, "little") + bytes(12) + b"\x03\x01"
    return body + inner + bytes(size - len(body) - len(inner))
cab0, cab1 = mkcab(200, b"..MSCF.."), mkcab(400)   # an 'MSCF' inside cab0 must not start a new cab
bundle = b"MZ" + bytes(100) + cab0 + cab1 + b"SIGNATURE-TAIL"
bf = P(tmp) / "bundle.exe"; bf.write_bytes(bundle)
ok(S.carve_cabs(bf) == [(102, 302), (302, 702)], f"carve_cabs finds both containers, ignores nested 'MSCF': {S.carve_cabs(bf)}")
(P(tmp) / "plain.exe").write_bytes(b"MZ" + bytes(50) + b"MSCF" + bytes(30))
ok(S.carve_cabs(P(tmp) / "plain.exe") == [], "carve_cabs ignores invalid headers")
MANIFEST = (b'<?xml version="1.0"?><BurnManifest xmlns="http://schemas.microsoft.com/wix/2008/Burn">'
            b'<UX><Payload Id="u" FilePath="thm.xml" Packaging="embedded" SourcePath="u0" Container="WixUXContainer"/></UX>'
            b'<Payload Id="p1" FilePath="core.msi" Packaging="embedded" SourcePath="a0" Container="WixAttachedContainer"/>'
            b'<Payload Id="p2" FilePath="core_AMD64.cab" Packaging="embedded" SourcePath="a1" Container="WixAttachedContainer"/>'
            b'<Payload Id="p3" FilePath="exe.msi" Packaging="embedded" SourcePath="a2" Container="WixAttachedContainer"/>'
            b'<Payload Id="p4" FilePath="lib.msi" Packaging="embedded" SourcePath="a3" Container="WixAttachedContainer"/>'
            b'<Payload Id="p5" FilePath="tcltk.msi" Packaging="embedded" SourcePath="a4" Container="WixAttachedContainer"/>'
            b'<Payload Id="p6" FilePath="../evil.msi" Packaging="embedded" SourcePath="a5" Container="WixAttachedContainer"/>'
            b'<Payload Id="p7" FilePath="core_d.msi" Packaging="download" SourcePath="a6" DownloadUrl="http://x"/></BurnManifest>')
pl = S.burn_payloads(MANIFEST)
ok(("core.msi", "a0") in pl and ("core_d.msi", "a6") not in pl and ("thm.xml", "u0") not in pl and len(pl) == 6, f"burn_payloads: embedded, non-UX only: {pl}")
S.find_expand = lambda: "expand"
def bundle_run(cmd, cwd=None):
    cmd = [str(c) for c in cmd]; cmds.append(cmd)
    if cmd[0] == "expand":
        k = int(P(cmd[1]).stem[1:]); out = P(cmd[3])
        for n in (["0", "u0"] if k == 0 else ["a0", "a1", "a2", "a3", "a4", "a5"]):
            (out / n).write_bytes(MANIFEST if n == "0" else b"data-" + n.encode())
        return 0
    return portable_run(cmd, cwd)
app.run = bundle_run; cmds.clear()
lay = P(tmp) / "lay_test" / "layout"; (lay.parent).mkdir()
ok(app.extract_bundle(bf, lay) is True and (lay / "core.msi").is_file() and (lay / "core_AMD64.cab").is_file() and (lay / "tcltk.msi").is_file(), "extract_bundle rebuilds the layout folder from the bundle")
ok(not (lay.parent / "evil.msi").exists() and not (P(tmp) / "lay_test" / "evil.msi").exists(), "unsafe '../' payload path is skipped")
ok(not any("/layout" in c for c in cmds), "extract_bundle never runs the installer")
# full flow through the direct path, into an EMPTY folder chosen by the user
inst_b = inst_dir / "python-3.8.10.exe"; inst_b.write_bytes(bundle)
ebase = P(tmp) / "empty_dest" / "python-3.8.10-x86"; ebase.mkdir(parents=True)
cmds.clear()
ok(app.t_local_installer(inst_b, ebase, direct=True) is True, "t_local_installer via direct bundle reading")
ok(all((ebase / f).is_file() for f in ("python.exe", "python312.dll", "Lib/os.py", "DLLs/_tkinter.pyd")) and not (ebase / "Python-3.8.10-32bit").exists(), "empty chosen folder is used DIRECTLY (no extra subfolder)")
ok(not any("/layout" in c for c in cmds) and any(c[0] == "expand" for c in cmds), "no /layout needed when the bundle can be read")
# expand failure -> falls back to /layout
def expand_fails(cmd, cwd=None):
    if str(cmd[0]) == "expand": return 1
    return portable_run(cmd, cwd)
app.run = expand_fails; cmds.clear(); fb = P(tmp) / "fb_empty"; fb.mkdir()
ok(app.t_local_installer(inst_b, fb, direct=True) is True and any("/layout" in c for c in cmds) and (fb / "python.exe").is_file(), "direct read fails -> fallback to /layout works")
# failure inside the user's own empty folder: folder kept, nothing left behind
app.run = lambda cmd, cwd=None: 1; ke = P(tmp) / "fail_empty"; ke.mkdir()
ok(app.t_local_installer(inst_b, ke, direct=True) is False and ke.is_dir() and not any(ke.iterdir()), "failure keeps the user's empty folder, leaves it empty")
# folder with other content -> subfolder, existing files untouched
app.run = bundle_run; ne = P(tmp) / "nonempty"; ne.mkdir(); (ne / "docs.txt").write_text("keep")
ok(app.t_local_installer(inst_b, ne) is True and (ne / "Python-3.8.10-32bit" / "python.exe").is_file() and (ne / "docs.txt").read_text() == "keep" and not (ne / "python.exe").exists(), "non-empty folder -> Python-<ver>-<bits>bit subfolder, files untouched")
S.find_expand = lambda: None

# ---------- scan diagnostics (why is my runtime not detected?)
dg = P(tmp) / "diag"; (dg / "Python-3.8.0-x64").mkdir(parents=True); (dg / "Python-3.8.0-x64" / "python.exe").symlink_to("/bin/false")
(dg / "emptyfolder").mkdir()
rep_ = {}
res = S.discover_pythons([str(dg), str(P(tmp) / "no_such_folder"), str(dg / "emptyfolder")], [], rep_)
ok(not any("diag" in i["path"] for i in res), "a python.exe that cannot run is not listed as a runtime")
ok(any("python.exe" in pth and "kode keluar" in why for pth, why in rep_["failed"]), f"failure reason reported: {rep_['failed']}")
ok((str(P(tmp) / "no_such_folder"), False, 0) in rep_["roots"] and (str(dg / "emptyfolder"), True, 0) in rep_["roots"] and (str(dg), True, 1) in rep_["roots"], f"per-folder scan report: {rep_['roots']}")
why = []; ok(S.probe_python(str(dg / "Python-3.8.0-x64" / "python.exe"), why) is None and why, "probe_python returns the reason")
app.logbuf.clear(); app.set_interps(res, rep_)
logtxt = "".join(app.logbuf)
ok("Folder yang dipindai" in logtxt and "Folder TIDAK ADA" in logtxt and "Tidak ada python.exe di" in logtxt and "tidak bisa dijalankan" in logtxt, "scan log explains missing/empty folders and unrunnable python.exe")

# ---------- deeper fallback search + richer failure reason
dp = P(tmp) / "deeproot"; nest = dp / "Portable Python-3.8.0 x64" / "App" / "Tools" / "Python"; nest.mkdir(parents=True); (nest / "python.exe").symlink_to(sys.executable)
ok(S.scan_dir_for_pythons(dp) == [], "normal scan (depth 2, skips Tools) does not reach a deeply nested python.exe")
rp = {}; got_ = S.discover_pythons([str(dp)], [], rp)
ok(len(got_) == 1 and rp.get("deep") and "Python" in rp["deep"][0], f"discover_pythons falls back to the deeper search: {rp.get('deep')}")
ok(S.scan_dir_for_pythons(dp, 8, skip=False, limit=2) == [], "deep search honours the folder limit")
bd = P(tmp) / "broken" / "py"; bd.mkdir(parents=True); (bd / "python.exe").symlink_to("/bin/false")
w2 = []; S.probe_python(str(bd / "python.exe"), w2)
ok("python3x.dll: TIDAK ADA" in w2[0] and "vcruntime140.dll" in w2[0], f"failure reason lists the missing DLL files: {w2[0]}")

# ---------- NEW: fixed Python folder, scrollable list with unrunnable entries
ok(S.PYTHON_DIR == S.APP_DIR / "Python" or str(S.PYTHON_DIR).endswith("Python"), "PYTHON_DIR is a folder named Python")
c0 = S.ensure_python_dir(); ok(c0 == (False, None), "ensure_python_dir: existing folder -> (False, None)")
shutil.rmtree(S.PYTHON_DIR); ok(S.ensure_python_dir() == (True, None) and S.PYTHON_DIR.is_dir(), "ensure_python_dir creates a missing folder")
real = S.PYTHON_DIR; blocker = P(tmp) / "afile"; blocker.write_text("x"); S.PYTHON_DIR = blocker / "Python"
cr, er = S.ensure_python_dir(); ok(cr is False and er, f"ensure_python_dir reports an error instead of crashing: {er[:40]}")
S.PYTHON_DIR = real
app.logbuf.clear(); ctk.CTkLabel.reset_mock(); ctk.CTkLabel.return_value.configure.reset_mock()
app.interps = [dict(by["Python-3.8.10-32bit"])]; app.broken = [("C:/Python/x/python.exe", "kode keluar 1")]
app.render_runtimes()
lbl = [c.kwargs.get("text", "") for c in ctk.CTkLabel.call_args_list]
ok(any("tidak bisa dijalankan" in l and "kode keluar 1" in l for l in lbl), "unrunnable python.exe is listed (with reason) instead of hidden")
ok(any("Runtime Python terdeteksi (2)" in str(c) for c in ctk.CTkLabel.return_value.configure.call_args_list), "list title shows the total number of Pythons")
app.interps, app.broken = [], []; ctk.CTkLabel.reset_mock(); app.render_runtimes()
ok(any("belum ada Python" in c.kwargs.get("text", "").lower() or "Belum ada Python" in c.kwargs.get("text", "") for c in ctk.CTkLabel.call_args_list), "empty folder -> clear hint")
# mouse wheel isolation
class Outer:
    def check_if_master_is_canvas(self, w): return True
class W:
    def __init__(self, master=None): self.master = master
o, inner = Outer(), W(); child = W(W(inner)); other = W(W())
app.isolate_wheel(o, inner)
ok(o.check_if_master_is_canvas(child) is False and o.check_if_master_is_canvas(inner) is False and o.check_if_master_is_canvas(other) is True, "outer frame ignores wheel events over the inner list")
# file information widgets follow the master switch
app.fi_widgets = [MagicMock(), MagicMock()]; app.v_fi_on.set(False); app.on_fileinfo_toggle(save=False)
ok(all(w.configure.call_args.kwargs == {"state": "disabled"} for w in app.fi_widgets), "switch off -> fields disabled")
app.v_fi_on.set(True); app.on_fileinfo_toggle(save=False)
ok(all(w.configure.call_args.kwargs == {"state": "normal"} for w in app.fi_widgets), "switch on -> fields enabled")

# ---------- NEW: file information (version resource) + date created
ok(S.parse_file_version("1.0.0.0") == (1,0,0,0) and S.parse_file_version(" 2.5 ") == (2,5,0,0) and S.parse_file_version("7") == (7,0,0,0), "parse_file_version accepts 1-4 parts")
ok(all(S.parse_file_version(x) is None for x in ("", "a.b", "1.2.3.4.5", "1..2", "65536", "1.0.0.-1", "v1.0")), "parse_file_version rejects bad input")
from datetime import datetime as DT
now = DT(2026, 11, 5, 14, 30, 7)
ok(S.parse_created_date("", now) == now and S.parse_created_date("2020-02-29", now) == DT(2020, 2, 29, 14, 30, 7), "parse_created_date: empty = now, date keeps time of day")
ok(all(S.parse_created_date(x, now) is None for x in ("2020/01/01", "2021-02-30", "1975-01-01", "2100-01-01", "abc")), "parse_created_date rejects bad/out-of-range dates")
ns = {}
class Rec:
    def __init__(self, n): self.n = n
    def __call__(self, *a, **k): return (self.n, a, k)
for n in ("VSVersionInfo", "FixedFileInfo", "StringFileInfo", "StringTable", "StringStruct", "VarFileInfo", "VarStruct"): ns[n] = Rec(n)
info = dict(S.FILEINFO_DEFAULTS, version="1.2", company="PT Maju 'Jaya'", desc="", product="", copyright="", website="https://x.id", comment="catatan", lang="English (en-US)")
def table(vi):   # the StringTable call: ("StringTable", (name, [StringStruct...]), {})
    return vi[2]["kids"][0][1][0][0]
def strings(vi): return dict(t[1] for t in table(vi)[1][1])
def table_name(vi): return table(vi)[1][0]
def translation(vi): return vi[2]["kids"][1][1][0][0][1][1]
txt = S.build_version_info(info, 'My App', now)
ok(txt.isascii(), "version file is pure ASCII (©, quotes are escaped)")
vi = eval(txt, ns)
strs = strings(vi)
ok(strs["CompanyName"] == "PT Maju 'Jaya'" and strs["FileDescription"] == "My App" and strs["ProductName"] == "My App", f"defaults: description/product = app name: {strs}")
ok(strs["FileVersion"] == "1.2.0.0" and strs["ProductVersion"] == "1.2.0.0" and strs["OriginalFilename"] == "My App.exe" and strs["InternalName"] == "My App", "versions padded to 4 parts, file names filled")
ok(strs["LegalCopyright"] == "Copyright \u00a9 2026 PT Maju 'Jaya'" and strs["Comments"] == "catatan | https://x.id" and strs["Website"] == "https://x.id", "auto copyright (year + company); website appended to Comments")
ok(vi[2]["ffi"][2]["filevers"] == (1,2,0,0) and table_name(vi) == "040904B0" and translation(vi) == [1033, 1200], "numeric version, English table 040904B0, Translation [1033,1200]")
info2 = dict(info, lang="Indonesia (id-ID)", company="", website="", comment="", copyright="(c) Saya", product="Prod")
vi2 = eval(S.build_version_info(info2, "A", now), ns)
strs2 = strings(vi2)
ok("CompanyName" not in strs2 and "Comments" not in strs2 and "Website" not in strs2 and strs2["LegalCopyright"] == "(c) Saya" and strs2["ProductName"] == "Prod"
   and table_name(vi2) == "042104B0" and translation(vi2) == [1057, 1200], "empty optional fields are omitted; Indonesian table 042104B0")
evil = eval(S.build_version_info(dict(info, company="x'), __import__('os').system('boom') #", desc='a"b\\'), "E", now), ns)
ok(strings(evil)["CompanyName"] == "x'), __import__('os').system('boom') #", "hostile text stays a plain string (no code injection)")
try:
    import PyInstaller.utils.win32.versioninfo as vinfo
    vf = P(tmp) / "v.txt"; vf.write_text(txt, encoding="utf-8"); ok(vinfo.load_version_info_from_text_file(str(vf)) is not None, "real PyInstaller parses the version file")
except ImportError:
    print("SKIP real PyInstaller parse (PyInstaller not installed here)")
# Date created
tf = P(tmp) / "t.exe"; tf.write_bytes(b"x"); when = DT(2020, 5, 6, 7, 8, 9)
ok(S.set_file_times(tf, when) is True and abs(tf.stat().st_mtime - when.timestamp()) < 2, "set_file_times sets the file time (creation time via SetFileTime on Windows)")
# venv check
vd = P(tmp) / "vv"; vd.mkdir(); (vd / "pyvenv.cfg").write_text("home = " + str(P(tmp) / "pyA") + "\ninclude-system-site-packages = false\n")
ok(S.venv_matches(vd, str(P(tmp) / "pyA" / "python.exe")) and not S.venv_matches(vd, str(P(tmp) / "pyB" / "python.exe")) and not S.venv_matches(P(tmp) / "none", "x/python.exe"), "venv_matches: same home ok, moved Python folder / missing cfg -> stale")

# ---------- NEW: build wiring (version file, date, stale venv) with a fake PyInstaller
app.run = lambda *a, **k: 0
src = P(tmp) / "proj" / "hello.py"; src.parent.mkdir(); src.write_text("print(1)")
outd = P(tmp) / "proj" / "dist_exe"
# invalid inputs stop the build before anything runs
app.sel = {"path": "py", "ver": (3, 12, 10), "bits": 64, "tk": True, "tkv": "", "pyi": None}
app.v_script.set(str(src)); app.v_name.set("hello"); app.v_out.set(str(outd)); app.v_fi_on.set(True); app.v_pkgs.set(""); app.v_icon.set("")  # real tk vars default to "" (the stub gives None)
app.v_fi["version"].set("1.x"); app.busy = False; app.logbuf.clear(); app.start_build()
ok(app.busy is False and "Versi aplikasi tidak valid" in "".join(app.logbuf), "invalid version stops the build with a clear message")
app.v_fi["version"].set("3.4.5"); app.v_fi["date"].set("31-12-2020"); app.v_fi_apply.set(True); app.logbuf.clear(); app.start_build()
ok(app.busy is False and "Tanggal dibuat tidak valid" in "".join(app.logbuf), "invalid date stops the build with a clear message")
cmds = []
def build_run(cmd, cwd=None):
    cmd = [str(c) for c in cmd]; cmds.append(cmd)
    if "PyInstaller" in cmd:
        e = P(cmd[cmd.index("--distpath") + 1]) / "hello.exe"; e.parent.mkdir(parents=True, exist_ok=True); e.write_bytes(b"MZ")
    return 0
app.run = build_run
stale = S.HOME / "venvs" / S.venv_tag(app.sel); (stale / "Scripts").mkdir(parents=True, exist_ok=True)
(stale / "Scripts" / "python.exe").write_text("old"); (stale / "pyvenv.cfg").write_text("home = /old/location\n")
def job(**kw):
    fi = dict(app.fileinfo_state(with_date=True), **kw)
    return dict(script=str(src), name="hello", out=str(outd), pkgs=[], icon="", one=True, gui=False, interp=app.sel, pi="pyinstaller",
                bg=False, admin=False, clean=False, kill=False, noupx=True, fi=fi)
app.v_fi["date"].set("2021-03-04"); app.q.queue.clear()
app.worker(job())
msgs = []
while not app.q.empty(): msgs.append(app.q.get())
dn = [m for m in msgs if m[0] == "done"]
pi_cmd = next(c for c in cmds if "PyInstaller" in c)
ok(dn and dn[0][1] is True, "worker succeeded with a fake PyInstaller")
ok("--version-file" in pi_cmd and P(pi_cmd[pi_cmd.index("--version-file") + 1]).read_text(encoding="utf-8").count("3, 4, 5, 0") == 2, "--version-file passed and holds the typed version")
ok(DT.fromtimestamp((outd / "hello.exe").stat().st_mtime).strftime("%Y-%m-%d") == "2021-03-04", "Date created/modified of the EXE set to the typed date")
ok(any("-m" in c and "venv" in c for c in cmds) and not (stale / "Scripts" / "python.exe").exists(), "stale venv (Python folder moved) was removed and recreated")
cmds.clear(); app.worker(job(enabled=False)); pi_cmd = next(c for c in cmds if "PyInstaller" in c)
ok("--version-file" not in pi_cmd, "switch off -> no version file")
(outd / "hello.exe").unlink(); cmds.clear(); app.worker(job(apply_date=False, date="2001-01-01"))
ok(abs((outd / "hello.exe").stat().st_mtime - time.time()) < 60, "'apply date' off -> file times untouched")

# ---------- NEW: Pythons installed on the PC are read and listed first; highest version first
ok(infos[0]["system"] is True and not any(i["system"] for i in infos[1:]), "extras are flagged system and sorted first; Python-folder entries are not system")
mk = lambda v, b, s: {"path": f"/x/{v}{b}{s}/python.exe", "ver": v, "bits": b, "system": s}
lst = sorted([mk((3,8,10),32,False), mk((3,12,4),64,False), mk((3,9,13),64,True), mk((3,13,0),64,True), mk((3,8,0),64,False), mk((3,8,10),64,False)], key=S.runtime_sort_key)
ok([(i["system"], i["ver"], i["bits"]) for i in lst] == [(True,(3,13,0),64),(True,(3,9,13),64),(False,(3,12,4),64),(False,(3,8,10),64),(False,(3,8,10),32),(False,(3,8,0),64)],
   "runtime_sort_key: PC first, then Python folder; each highest -> lowest version (64-bit before 32-bit)")
ok(S.runtime_sort_key({"path": "p", "ver": (3, 8), "bits": 64}) > S.runtime_sort_key({"path": "p", "ver": (3, 9, 1), "bits": 64}), "sort key tolerates a 2-part version")
W = r"D:\Example\Tools\Python-3.8.0 x64\App\Python\python.exe"
ok(S.guess_version_from_path(W) == (3, 8, 0) and S.guess_version_from_path(r"X:\Python\python-3.8.10-x86\python.exe") == (3, 8, 10)
   and S.guess_version_from_path(r"C:\Python312\python.exe") == (3, 12) and S.guess_version_from_path(r"C:\Tools\py\python.exe") is None, "guess_version_from_path")
sysroot = P(tmp) / "sysroot"
for sub in ("A", "WindowsApps", "venv/Scripts"):
    (sysroot / sub).mkdir(parents=True); (sysroot / sub / "python.exe").symlink_to(sys.executable)
(sysroot / "venv" / "pyvenv.cfg").write_text("x")
old_path = os.environ.get("PATH", "")
os.environ["PATH"] = os.pathsep.join([str(sysroot / "A"), str(sysroot / "A"), str(sysroot / "WindowsApps"), str(sysroot / "venv" / "Scripts"), str(sysroot / "nope")])
try:
    sp = S.find_system_pythons()
finally:
    os.environ["PATH"] = old_path
ok(sp == [os.path.abspath(sysroot / "A" / "python.exe")], f"find_system_pythons: PATH entry found once; WindowsApps stub, venv and missing dir skipped: {sp}")
ok(S.registry_pythons() == [], "registry_pythons is a no-op off Windows")
rs = S.discover_pythons([str(root)], sp)
ok(rs and rs[0]["system"] and rs[0]["path"] == sp[0] and not any(i["system"] for i in rs[1:]), "discover_pythons: system Python listed first")
inside = S.discover_pythons([str(root)], [str(root / "Python-3.8.10-32bit" / "python.exe")])
ok(not any(i["system"] for i in inside), "an 'extra' that lives inside the Python folder is not flagged as system")

# ---------- NEW v1.6.1: no needless download/uninstall during build
ok(S.venv_tag({"path": "/a/python.exe", "ver": (3, 8, 10), "bits": 64}) != S.venv_tag({"path": "/b/python.exe", "ver": (3, 8, 10), "bits": 64})
   and S.venv_tag({"path": "/a/python.exe", "ver": (3, 8, 10), "bits": 64}).startswith("py38-64-"), "venv_tag: same version, different python.exe -> different venv")
cmds.clear(); app.run = build_run
vt = S.HOME / "venvs" / S.venv_tag(app.sel)
shutil.rmtree(vt, ignore_errors=True)
def build_run_venv(cmd, cwd=None):
    r = build_run(cmd, cwd)
    c = [str(x) for x in cmd]
    if "venv" in c and "-m" in c:
        (vt / "Scripts").mkdir(parents=True, exist_ok=True); (vt / "Scripts" / "python.exe").write_text("v")
        (vt / "pyvenv.cfg").write_text("home = " + str(P(app.sel["path"]).parent) + "\n")
    return r
app.run = build_run_venv
app.worker(job()); first = [c for c in cmds]
ok(any("--upgrade" in c and "pip" in c for c in first), "new venv: pip upgraded once")
ok(not any("--upgrade" in c and "pyinstaller" in c for c in first), "PyInstaller is never installed with --upgrade during a build")
cmds.clear(); app.worker(job())
ok(not any("venv" in c and "-m" in c for c in cmds) and not any("--upgrade" in c for c in cmds), "2nd build: venv reused, no --upgrade at all")
# cache folder of other PyInstaller users is not touched
fake_cache = P(tmp) / "AppData" / "Local" / "pyinstaller"; fake_cache.mkdir(parents=True); (fake_cache / "x").write_text("keep")
os.environ["LOCALAPPDATA"] = str(P(tmp) / "AppData" / "Local")
cmds.clear(); app.worker(dict(job(), clean=True))
ok((fake_cache / "x").is_file(), "'clean' leaves %LOCALAPPDATA%\\pyinstaller alone")
ok(not any("--clean" in c for c in cmds if "PyInstaller" in c), "'clean' alone does NOT pass --clean to PyInstaller (shared cache untouched)")
cmds.clear(); app.worker(dict(job(), clean=True, deep=True))
ok(any("--clean" in c for c in cmds if "PyInstaller" in c), "'deep clean' passes --clean to PyInstaller")
cmds.clear(); app.worker(dict(job(), clean=False, deep=True))
ok(any("--clean" in c for c in cmds if "PyInstaller" in c), "'deep clean' works independently of the work-folder clean")
wk = S.HOME / "work" / S.hashlib.md5(str(src).encode()).hexdigest()[:8]; wk.mkdir(parents=True, exist_ok=True); (wk / "stale.txt").write_text("old")
app.worker(dict(job(), clean=True)); ok(not (wk / "stale.txt").exists(), "'clean' wipes the app's own work folder")
(wk / "stale.txt").write_text("old"); app.worker(dict(job(), clean=False)); ok((wk / "stale.txt").exists(), "clean off -> work folder kept (faster rebuilds)")
# library confirmation
app.run = lambda *a, **k: 0
app.v_fi["version"].set("1.0"); app.v_fi["date"].set(""); app.v_pkgs.set("requests, numpy"); app.busy = False
started = []; threading.Thread = type("T", (), {"__init__": lambda self, **k: started.append(k), "start": lambda self: None})
tk.messagebox.askyesnocancel = MagicMock(return_value=None); app.start_build()
ok(not started and app.busy is False, "Cancel in the library dialog aborts the build")
tk.messagebox.askyesnocancel = MagicMock(return_value=False); app.start_build()
ok(started and started[-1]["args"][0]["pkgs"] == [], "'No' builds without installing libraries")
started.clear(); app.busy = False; tk.messagebox.askyesnocancel = MagicMock(return_value=True); app.start_build()
ok(started and started[-1]["args"][0]["pkgs"] == ["requests", "numpy"], "'Yes' installs the detected libraries")

# ---------- NEW v1.6.3: dialog only for libraries that are NOT yet installed in the venv
inst = {"requests": "2.31.0", "pillow": "10.2.0", "pyyaml": "6.0.1", "numpy": "1.26.4+cpu"}
ok(S.normalize_pkg_name("Py_YAML.x") == "py-yaml-x", "normalize_pkg_name (PEP 503)")
ok(S.missing_packages(["requests", "Pillow", "PyYAML>=5", "numpy==1.26.4", "numpy==1.26.*"], inst) == [], "installed / matching pins -> nothing missing")
ok(S.missing_packages(["requests", "scipy", "numpy==1.20.0", "Pillow==9.*"], inst) == ["scipy", "numpy==1.20.0", "Pillow==9.*"], "uninstalled library or wrong pinned version -> missing")
ok(S.missing_packages(["a", "b"], None) == ["a", "b"] and S.missing_packages([], inst) == [], "unknown venv -> everything missing")
class RR:
    def __init__(self, out, rc=0): self.stdout, self.returncode = out, rc
real_qr = S.quiet_run
S.quiet_run = lambda cmd, **k: RR('[{"name": "Pillow", "version": "10.2.0"}, {"name": "customtkinter", "version": "5.2.2"}]')
ok(S.installed_packages("vpy") == {"pillow": "10.2.0", "customtkinter": "5.2.2"}, "installed_packages parses `pip list --format=json`")
S.quiet_run = lambda cmd, **k: RR("", 1); ok(S.installed_packages("vpy") is None, "pip list failure -> None (treated as unknown)")
def boom(cmd, **k): raise OSError("cannot run")
S.quiet_run = boom; ok(S.installed_packages("vpy") is None, "unrunnable venv python -> None")
S.quiet_run = real_qr
app.sel = {"path": "py", "ver": (3, 12, 10), "bits": 64, "tk": True, "tkv": "", "pyi": None}
ok(app.venv_installed() is None or isinstance(app.venv_installed(), dict), "venv_installed never raises")
shutil.rmtree(S.HOME / "venvs" / S.venv_tag(app.sel), ignore_errors=True)
ok(app.venv_installed() is None, "no venv yet -> None")
app.busy = False; app.v_pkgs.set("requests, numpy")
asked = MagicMock(return_value=True); tk.messagebox.askyesnocancel = asked
started.clear(); app.venv_installed = lambda: {"requests": "1", "numpy": "1"}; app.logbuf.clear(); app.start_build()
ok(not asked.called and started and started[-1]["args"][0]["pkgs"] == ["requests", "numpy"] and "sudah terpasang" in "".join(app.logbuf), "all installed -> NO dialog, build starts")
started.clear(); app.busy = False; app.venv_installed = lambda: {"requests": "1"}; app.start_build()
msg = asked.call_args[0][1]
ok(asked.called and "numpy" in msg and "requests" not in msg and started, "only the NOT installed library is listed in the dialog")
started.clear(); app.busy = False; asked.reset_mock(); app.venv_installed = lambda: None; app.start_build()
ok("requests" in asked.call_args[0][1] and "numpy" in asked.call_args[0][1], "no venv yet -> dialog lists everything")
started.clear(); app.busy = False; tk.messagebox.askyesnocancel = MagicMock(return_value=None); app.start_build()
ok(not started and app.busy is False, "Cancel still aborts")
del app.venv_installed

# ---------- NEW v1.6.4: app-name validation, absolute output folder, EXE must exist and be non-empty
ok(all(S.validate_app_name(n) is None for n in ("hello", "My App", "app.v2", "con1", "COM10", "a" * 100, "Aplikasi-Ku_2")), "validate_app_name accepts normal names")
ok(S.validate_app_name("")[0] == "empty" and S.validate_app_name("   ")[0] == "empty" and S.validate_app_name(None)[0] == "empty", "validate_app_name: empty")
ok(S.validate_app_name("a" * 101) == ("long", 100), "validate_app_name: too long")
ok(all(S.validate_app_name(f"a{c}b")[0] == "chars" for c in '<>:"/\\|?*') and S.validate_app_name("a\x01b")[0] == "chars" and S.validate_app_name("a\nb")[0] == "chars", "validate_app_name: forbidden characters / control characters")
ok(S.validate_app_name("app.")[0] == "edge" and S.validate_app_name(" app")[0] == "edge" and S.validate_app_name("app ")[0] == "edge", "validate_app_name: leading/trailing space or trailing dot")
ok(all(S.validate_app_name(n) == ("reserved", n.split(".")[0].upper()) for n in ("CON", "con", "Prn", "AUX", "nul", "COM1", "com9", "LPT1", "lpt9", "CON.txt", "nul.tar.gz")), "validate_app_name: reserved device names (any case, with extension)")
od, oe = S.normalize_output_dir("", P(tmp) / "dflt"); ok(od == str((P(tmp) / "dflt").resolve()) and oe is None, "normalize_output_dir: empty -> default, absolute")
os.chdir(tmp); od, oe = S.normalize_output_dir("rel/../dist", "x")
ok(od == str((P(tmp) / "dist").resolve()) and os.path.isabs(od) and ".." not in od, f"normalize_output_dir: relative path + '..' resolved to absolute: {od}")
od, _ = S.normalize_output_dir("~/out", "x"); ok(od == str((P.home() / "out").resolve()), "normalize_output_dir expands ~")
od, oe = S.normalize_output_dir("a\0b", "x"); ok(od is None and oe, "normalize_output_dir rejects a null character without crashing")

# start_build refuses bad names / bad output folder before anything starts
app.sel = {"path": "py", "ver": (3, 12, 10), "bits": 64, "tk": True, "tkv": "", "pyi": None}
app.v_script.set(str(src)); app.v_pkgs.set(""); app.v_fi_on.set(False); app.v_out.set(str(outd)); app.busy = False
for bad_name, frag in (("CON", "nama perangkat khusus Windows"), ("a:b", "karakter terlarang"), ("app.", "berakhiran titik")):
    app.v_name.set(bad_name); app.logbuf.clear(); app.start_build()
    ok(app.busy is False and "Nama aplikasi tidak valid" in "".join(app.logbuf) and frag in "".join(app.logbuf), f"start_build rejects name {bad_name!r}")
app.v_name.set("hello"); app.v_out.set("a\0b"); app.logbuf.clear(); app.start_build()
ok(app.busy is False and "Folder keluaran tidak valid" in "".join(app.logbuf), "start_build rejects an invalid output folder")
app.lang = "en"; app.v_name.set("NUL"); app.v_out.set(str(outd)); app.logbuf.clear(); app.start_build()
ok("reserved Windows device name" in "".join(app.logbuf), "English message works too"); app.lang = "id"
# a relative output folder reaches the worker as an absolute path
started.clear(); app.busy = False; app.v_name.set("hello"); app.v_out.set("rel_out"); tk.messagebox.askyesnocancel = MagicMock(return_value=True); app.start_build()
ok(started and os.path.isabs(started[-1]["args"][0]["out"]) and started[-1]["args"][0]["out"].endswith("rel_out"), "relative output folder is passed to the worker as an absolute path")
started.clear(); app.busy = False

# worker: exit code 0 is not enough - the EXE must exist and have content
def run_ok_no_exe(cmd, cwd=None): return 0
def run_ok_empty_exe(cmd, cwd=None):
    cmd = [str(c) for c in cmd]
    if "PyInstaller" in cmd:
        e = P(cmd[cmd.index("--distpath") + 1]) / "hello.exe"; e.parent.mkdir(parents=True, exist_ok=True); e.write_bytes(b"")
    return 0
shutil.rmtree(outd, ignore_errors=True)
for fake, why in ((run_ok_no_exe, "missing"), (run_ok_empty_exe, "empty (0 bytes)")):
    app.run = fake; app.q.queue.clear(); app.worker(job(enabled=False))
    m = []
    while not app.q.empty(): m.append(app.q.get())
    d = [x for x in m if x[0] == "done"]; txt = "".join(x[1] for x in m if x[0] == "log")
    ok(d and d[0][1] is False and ("tidak ditemukan" if why == "missing" else "kosong") in txt, f"exit code 0 but EXE {why} -> build reported as FAILED (no false success)")
# one-folder build is checked at <name>/<name>.exe
def run_onedir(cmd, cwd=None):
    cmd = [str(c) for c in cmd]
    if "PyInstaller" in cmd:
        e = P(cmd[cmd.index("--distpath") + 1]) / "hello" / "hello.exe"; e.parent.mkdir(parents=True, exist_ok=True); e.write_bytes(b"MZ")
    return 0
app.run = run_onedir; app.q.queue.clear(); app.worker(dict(job(enabled=False), one=False))
m = []
while not app.q.empty(): m.append(app.q.get())
ok([x for x in m if x[0] == "done"][0][1] is True, "one-folder build with a real EXE inside <name>/ succeeds")
app.run = build_run

# ---------- NEW v1.6.5: deep-clean option is persisted, default off, and has its own label
ok(S.OPTION_DEFAULTS["deepclean"] is False and S.OPTION_DEFAULTS["clean"] is True, "defaults: work-folder clean ON, deep clean OFF")
app.v_deep.set(True); app.save_cfg(); ok(json.loads(S.CONFIG_FILE.read_text())["opts"]["deepclean"] is True, "deep clean is saved to config")
ok(S.App().v_deep.get() is True, "...and restored on next start")
app.v_deep.set(False); app.save_cfg()
ok("deepclean" in S.STRINGS["id"] and "deepclean" in S.STRINGS["en"] and "PyInstaller" in S.STRINGS["id"]["deepclean"], "deep-clean label exists in both languages")
ctk.CTkSwitch.reset_mock(); app.build_ui()
sw = [c.kwargs.get("text") for c in ctk.CTkSwitch.call_args_list]
ok(S.STRINGS["id"]["clean"] in sw and S.STRINGS["id"]["deepclean"] in sw, "both clean switches are rendered")

print("\nALL LOGIC TESTS PASSED")
