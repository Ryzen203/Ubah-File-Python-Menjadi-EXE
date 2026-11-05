"""Privacy check before publishing to GitHub / attaching an EXE to a Release.

Scans files for personal traces: your Windows user name, your user-profile folder,
absolute drive paths (C:\\Users\\..., D:\\...) and any extra words you pass with --term.
Text files are read as UTF-8; binaries (EXE) are searched as ASCII and UTF-16.

Usage:
    python tools/check_privacy.py                       # scan the whole project
    python tools/check_privacy.py "dist/PyCompiler Studio.exe"
    python tools/check_privacy.py --term "NamaSaya" --term "PROYEK CLAUDE"
Exit code 0 = clean, 1 = something found.
"""
import argparse
import getpass
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "build", "dist", "dist_exe", "Python", ".venv", "venv"}
BINARY_EXT = {".exe", ".dll", ".pyd", ".zip", ".png", ".jpg", ".ico", ".pyc"}
# absolute Windows paths; the generic examples used in the tests are allowed
DRIVE_PATH = re.compile(r"\b[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\\/\s\"']+", re.I)
ALLOWED = ("Example", "<user>", "%USERNAME%", "USERNAME", "Public", "Default")


def terms_from_system(extra):
    out = {t for t in extra if t}
    for v in (getpass.getuser(), os.environ.get("USERNAME", ""), Path.home().name):
        if v and len(v) >= 3 and v.lower() not in ("user", "admin", "root"):
            out.add(v)
    return sorted(out, key=str.lower)


def scan_text(path, terms):
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for t in terms:
            if t.lower() in low:
                hits.append((n, f"contains '{t}'", line.strip()[:120]))
        for m in DRIVE_PATH.finditer(line):
            if not any(a.lower() in m.group(0).lower() for a in ALLOWED):
                hits.append((n, "absolute user path", m.group(0)))
    return hits


def scan_binary(path, terms):
    data = path.read_bytes()
    hits = []
    for t in terms:
        for enc in ("ascii", "utf-16-le"):
            if t.encode(enc, "ignore") and t.encode(enc, "ignore").lower() in data.lower():
                hits.append((0, f"binary contains '{t}' ({enc})", ""))
    for m in re.finditer(rb"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\x00\s]{1,40}", data):
        s = m.group(0).decode("ascii", "ignore")
        if not any(a.lower() in s.lower() for a in ALLOWED):
            hits.append((0, "binary contains absolute user path", s))
            break
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files/folders to scan (default: project root)")
    ap.add_argument("--term", action="append", default=[], help="extra word to look for (repeatable)")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    targets = [Path(p) for p in a.paths] or [root]
    terms = terms_from_system(a.term)
    print("Looking for:", ", ".join(terms) or "(no user name found)", "+ absolute user paths")
    bad = 0
    for t in targets:
        files = [t] if t.is_file() else [f for f in t.rglob("*") if f.is_file()
                                         and not (set(f.relative_to(t).parts) & SKIP_DIRS)]
        for f in files:
            if f.resolve() == Path(__file__).resolve():
                continue
            hits = scan_binary(f, terms) if f.suffix.lower() in BINARY_EXT else scan_text(f, terms)
            for n, why, ctx in hits:
                bad += 1
                print(f"FOUND  {f}{':' + str(n) if n else ''}  {why}  {ctx}")
    print("CLEAN - nothing personal found." if not bad else f"\n{bad} finding(s). Fix them before publishing.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
