#!/usr/bin/env python3
"""
hoi4_scan.py - interactive, guided HOI4 memory scanner. Run it and follow the
prompts; no Python knowledge or code-pasting needed.

Run from Windows PowerShell, AS ADMINISTRATOR, with HOI4 running and a save loaded:
    cd "C:\\Users\\Brock\\Documents\\My Cheat Tables\\HOI4-Memory-Toolkit"
    python tools\\hoi4_scan.py

It does Cheat Engine's value-scan in a guided loop: type a number you can read off
the HOI4 UI; it finds every matching address; change the number in-game and type the
new value to narrow down until one address remains; then set it.
Multipliers (triangulated from proven tables): Political Power & Stability x1000,
Army/Navy/Air XP x32768. Every step is logged to logs/hoi4_scan.log.
"""
import ctypes
import struct
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "logs" / "hoi4_scan.log"


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


if sys.platform != "win32":
    sys.exit("Run this with WINDOWS Python, as Administrator (it reads hoi4.exe memory).")

k = ctypes.WinDLL("kernel32", use_last_error=True)
LP, ST, DW, BL, HD = ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_int, ctypes.c_void_p
for _fn, _a, _r in [("OpenProcess", [DW, BL, DW], HD), ("CreateToolhelp32Snapshot", [DW, DW], HD),
                    ("Process32FirstW", [HD, LP], BL), ("Process32NextW", [HD, LP], BL),
                    ("CloseHandle", [HD], BL), ("VirtualQueryEx", [HD, LP, LP, ST], ST),
                    ("ReadProcessMemory", [HD, LP, LP, ST, LP], BL),
                    ("WriteProcessMemory", [HD, LP, LP, ST, LP], BL)]:
    getattr(k, _fn).argtypes = _a
    getattr(k, _fn).restype = _r


class MBI(ctypes.Structure):
    _fields_ = [("Base", HD), ("Alloc", HD), ("AllocProt", DW), ("Size", ST),
                ("State", DW), ("Protect", DW), ("Type", DW)]


class PE(ctypes.Structure):
    _fields_ = [("dwSize", DW), ("u", DW), ("pid", DW), ("heap", HD), ("mod", DW),
                ("thr", DW), ("par", DW), ("pri", ctypes.c_long), ("flags", DW),
                ("exe", ctypes.c_wchar * 260)]


WRITABLE = {0x04, 0x08, 0x40, 0x80}


def find_pid(name="hoi4.exe"):
    s = k.CreateToolhelp32Snapshot(2, 0)
    e = PE()
    e.dwSize = ctypes.sizeof(e)
    ok = k.Process32FirstW(s, ctypes.byref(e))
    pid = None
    while ok:
        if e.exe.lower() == name:
            pid = e.pid
            break
        ok = k.Process32NextW(s, ctypes.byref(e))
    k.CloseHandle(s)
    return pid


def regions(h):
    m = MBI()
    a = 0
    sz = ctypes.sizeof(m)
    while a < 0x7FFFFFFFFFFF:
        if k.VirtualQueryEx(h, ctypes.c_void_p(a), ctypes.byref(m), sz) != sz:
            break
        b = m.Base or 0
        r = m.Size or 0
        if r == 0:
            break
        if m.State == 0x1000 and m.Protect in WRITABLE and not (m.Protect & 0x100):
            yield b, r
        a = b + r


def read(h, a, n):
    buf = (ctypes.c_char * n)()
    got = ST(0)
    if k.ReadProcessMemory(h, ctypes.c_void_p(a), buf, n, ctypes.byref(got)) and got.value:
        return bytes(buf[:got.value])
    return None


def first_scan(h, v):
    p = struct.pack("<i", v)
    out = []
    t = time.time()
    for b, r in regions(h):
        o = 0
        while o < r:
            n = min(4194304, r - o)
            d = read(h, b + o, n)
            if d:
                i = d.find(p)
                while i >= 0:
                    out.append(b + o + i)
                    i = d.find(p, i + 1)
            o += n - 3 if n == 4194304 else n
            if len(out) > 400000:
                break
        if len(out) > 400000:
            break
    out = sorted(set(out))
    log(f"scan {v} -> {len(out)} hits in {time.time() - t:.1f}s")
    return out


def narrow(h, cands, v):
    p = struct.pack("<i", v)
    out = [a for a in cands if read(h, a, 4) == p]
    log(f"narrow {v} -> {len(out)} hits")
    return out


def main():
    pid = find_pid()
    if not pid:
        sys.exit("hoi4.exe not running - launch the game and load a save first.")
    h = k.OpenProcess(0x1F0FFF, False, pid)
    if not h:
        sys.exit("OpenProcess failed - close this, RIGHT-CLICK PowerShell, 'Run as administrator', retry.")
    log(f"attached to hoi4.exe pid={pid}")
    print("\nMultipliers: Political Power & Stability = x1000, Army/Navy/Air XP = x32768.")
    print("Example: 247 Political Power -> type 247000.\n")
    try:
        v = int(input("Value to search for (number x multiplier): ").strip())
    except ValueError:
        sys.exit("not a number")
    print("scanning, please wait (a few seconds)...")
    cands = first_scan(h, v)
    shown = str([hex(a) for a in cands]) if len(cands) <= 12 else "(change it in-game, then narrow)"
    print(f"-> {len(cands)} candidate addresses. {shown}")
    while True:
        print("\nChange that value IN-GAME, then type its NEW number to narrow it down.")
        s = input("New value  |  'w 5000000' to set the single address  |  'q' to quit: ").strip()
        if s.lower() in ("q", "quit", ""):
            break
        if s.lower().startswith("w "):
            try:
                val = int(s[2:].strip())
            except ValueError:
                print("bad write value")
                continue
            if len(cands) != 1:
                print(f"refusing: {len(cands)} candidates - narrow to exactly 1 first.")
                continue
            w = ST(0)
            ok = k.WriteProcessMemory(h, ctypes.c_void_p(cands[0]), struct.pack("<i", val), 4, ctypes.byref(w))
            log(f"WRITE {hex(cands[0])} = {val} -> {'OK' if ok and w.value == 4 else 'FAILED'}")
            continue
        try:
            nv = int(s)
        except ValueError:
            print("enter a number, 'w VALUE', or 'q'")
            continue
        cands = narrow(h, cands, nv)
        shown = str([hex(a) for a in cands]) if len(cands) <= 20 else ""
        print(f"-> {len(cands)} candidates. {shown}")
    k.CloseHandle(h)
    print("done. Full log: logs/hoi4_scan.log")


if __name__ == "__main__":
    main()
