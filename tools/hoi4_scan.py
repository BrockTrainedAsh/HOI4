#!/usr/bin/env python3
"""
hoi4_scan.py - interactive, guided HOI4 memory scanner. Run it, follow the prompts.

Run from Windows PowerShell, AS ADMINISTRATOR, with HOI4 running and a save loaded:
    python "C:\\Users\\Brock\\Documents\\My Cheat Tables\\HOI4-Memory-Toolkit\\tools\\hoi4_scan.py"

KEY IDEA - displayed numbers hide decimals. HOI4 stores Political Power x1000, so
"7 PP" on the bar is really 7000-7999 in memory (7.34 PP = 7340). So we scan a
RANGE, not an exact value, and then narrow with 'up'/'down' as the value changes -
which never needs the exact number. Multipliers (triangulated from proven tables):
Political Power & Stability x1000, Army/Navy/Air XP x32768, Manpower x1.

Everything is logged to logs/hoi4_scan.log.
"""
import array
import ctypes
import json
import struct
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "logs" / "hoi4_scan.log"
CAND = Path(__file__).resolve().parent.parent / "logs" / "hoi4_candidates.json"


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def save_cands(cands, mult):
    """Persist the current candidate addresses so hoi4_watch.py can watch them."""
    try:
        CAND.parent.mkdir(parents=True, exist_ok=True)
        CAND.write_text(json.dumps({"mult": mult, "addrs": sorted(int(a) for a in cands)}))
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


def range_scan(h, lo, hi):
    """Find all 4-byte-aligned int32 values in [lo, hi]. Returns {addr: value}."""
    out = {}
    t = time.time()
    done_mb = 0
    for b, r in regions(h):
        o = 0
        while o < r:
            n = min(4194304, r - o)
            d = read(h, b + o, n)
            if d:
                cnt = len(d) // 4
                arr = array.array("i")
                arr.frombytes(d[:cnt * 4])
                out.update((b + o + i * 4, v) for i, v in enumerate(arr) if lo <= v <= hi)
                done_mb += n // (1024 * 1024)
            o += n
            if len(out) > 400000:
                log("hit 400k cap - value too common; pick a more distinctive number")
                return out, time.time() - t
    return out, time.time() - t


def narrow_range(h, cands, lo, hi):
    out = {}
    for a in cands:
        d = read(h, a, 4)
        if d:
            v = struct.unpack("<i", d)[0]
            if lo <= v <= hi:
                out[a] = v
    return out


def narrow_cmp(h, cands, mode):
    out = {}
    for a, old in cands.items():
        d = read(h, a, 4)
        if not d:
            continue
        v = struct.unpack("<i", d)[0]
        keep = ((mode == "up" and v > old) or (mode == "down" and v < old)
                or (mode == "same" and v == old) or (mode == "changed" and v != old))
        if keep:
            out[a] = v
    return out


def show(cands, mult):
    items = sorted(cands.items())
    if len(items) <= 25:
        for a, v in items:
            print(f"    0x{a:X} = {v}  (~{v / mult:.3f})")


def main():
    pid = find_pid()
    if not pid:
        sys.exit("hoi4.exe not running - launch the game and load a save first.")
    h = k.OpenProcess(0x1F0FFF, False, pid)
    if not h:
        sys.exit("OpenProcess failed - close this, run PowerShell as Administrator, retry.")
    log(f"attached to hoi4.exe pid={pid}")
    print("\nMultipliers: Political Power & Stability x1000, XP x32768, Manpower x1.")
    try:
        disp = int(input("Current displayed value (e.g. Political Power = 7): ").strip())
        mult = int((input("Multiplier [Enter = 1000]: ").strip() or "1000"))
    except ValueError:
        sys.exit("not a number")
    lo, hi = disp * mult, (disp + 1) * mult - 1
    print(f"scanning for any value in [{lo}, {hi}] - please wait (can take ~1 min)...")
    cands, secs = range_scan(h, lo, hi)
    log(f"range scan [{lo},{hi}] -> {len(cands)} candidates in {secs:.0f}s")
    show(cands, mult)
    while len(cands) != 0:
        print("\nNarrow it down. Best method: change the value IN-GAME, then:")
        print("  up / down   = keep addresses whose value increased / decreased")
        print("  <number>    = new displayed value (range narrow, e.g. PP is now 9 -> type 9)")
        print("  w <number>  = SET the value (only when 1 candidate left), e.g. w 5000")
        print("  l = list,  q = quit")
        s = input("> ").strip().lower()
        if s in ("q", "quit", ""):
            break
        if s == "l":
            show(cands, mult)
            continue
        if s in ("up", "down", "same", "changed"):
            cands = narrow_cmp(h, cands, s)
        elif s.startswith("w "):
            try:
                target = int(s[2:].strip())
            except ValueError:
                print("bad value")
                continue
            if len(cands) != 1:
                print(f"refusing: {len(cands)} candidates - narrow to exactly 1 first.")
                continue
            addr = next(iter(cands))
            w = ST(0)
            ok = k.WriteProcessMemory(h, ctypes.c_void_p(addr),
                                      struct.pack("<i", target * mult), 4, ctypes.byref(w))
            log(f"WRITE 0x{addr:X} = {target * mult} ({target}) -> "
                f"{'OK' if ok and w.value == 4 else 'FAILED err ' + str(ctypes.get_last_error())}")
            continue
        else:
            try:
                nd = int(s)
            except ValueError:
                print("type up / down / a number / 'w <n>' / q")
                continue
            cands = narrow_range(h, cands, nd * mult, (nd + 1) * mult - 1)
        log(f"-> {len(cands)} candidates")
        show(cands, mult)
    if len(cands) == 0:
        print("0 candidates - the value moved out of every tracked range. Re-run and use "
              "'up'/'down' instead of typing exact numbers (more robust to decimals).")
    k.CloseHandle(h)
    print("done. Full log: logs/hoi4_scan.log")


if __name__ == "__main__":
    main()
