#!/usr/bin/env python3
"""
hoi4_mem.py - scriptable HOI4 memory scanner/editor with a log the agent can read.

This is the proven approach (what FearLess Revolution / Recifense / Hexorg tables do):
find a value in hoi4.exe's memory and write it directly. It does in a script what
Cheat Engine does in a GUI - but it writes every step to logs/hoi4_mem.log, so the
findings can be reviewed and diagnosed instead of being trapped in CE's window.

IMPORTANT: run this with WINDOWS Python, AS ADMINISTRATOR (it opens hoi4.exe with
VM_READ/VM_WRITE). It is Windows-only (uses ctypes + the Win32 API). Stdlib only.

Triangulated value facts (Hexorg v1.2/v1.3 + Recifense 1.11.10 all agree):
  Political Power  -> int32, value x1000   (e.g. 247 PP is stored as 247000)
  Army/Navy/Air XP -> int32, value x32768
  Stability/WarSup -> int32, value x1000   (modern versions)

Typical workflow (mirrors Cheat Engine's "unknown -> next scan"):
  1) python hoi4_mem.py scan 247000          # your current PP x1000
  2) spend/gain some PP in-game, then:
  3) python hoi4_mem.py next 251000          # narrows the candidates
  4) repeat next until 1 address remains, then:
  5) python hoi4_mem.py write <addr> 5000000 # set PP to 5000 (5000 x1000)

Examples:
  python hoi4_mem.py info
  python hoi4_mem.py scan 247000 --type i32
  python hoi4_mem.py next 251000
  python hoi4_mem.py list
  python hoi4_mem.py read 0x1A2B3C4D0
  python hoi4_mem.py write 0x1A2B3C4D0 5000000
"""
import argparse
import array
import ctypes
import json
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGFILE = ROOT / "logs" / "hoi4_mem.log"
CANDFILE = ROOT / "logs" / "hoi4_mem_candidates.json"
RANGEFILE = ROOT / "logs" / "hoi4_mem_range.json"
SHOTDIR = ROOT / "logs" / "watch"
MAX_CANDS = 400_000
CHUNK = 4 * 1024 * 1024

# --- access + memory constants -------------------------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
WRITABLE = {0x04, 0x08, 0x40, 0x80}  # RW, WRITECOPY, EXEC_RW, EXEC_WRITECOPY

TH32CS_SNAPPROCESS = 0x00000002

# struct (fmt, size, signed) per type name
TYPES = {
    "i32": ("<i", 4), "u32": ("<I", 4), "i64": ("<q", 8),
    "float": ("<f", 4), "double": ("<d", 8),
}


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line)
    try:
        LOGFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _k32():
    if sys.platform != "win32":
        sys.exit("hoi4_mem.py must run under WINDOWS Python as admin "
                 "(it reads hoi4.exe memory via the Win32 API).")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    # CRITICAL on 64-bit: declare prototypes so handles/pointers are not truncated
    # to 32 bits (the default ctypes restype is c_int).
    LP, ST, DW, BL, HD = (ctypes.c_void_p, ctypes.c_size_t,
                          ctypes.c_ulong, ctypes.c_int, ctypes.c_void_p)
    k.OpenProcess.argtypes = [DW, BL, DW]; k.OpenProcess.restype = HD
    k.CreateToolhelp32Snapshot.argtypes = [DW, DW]; k.CreateToolhelp32Snapshot.restype = HD
    k.Process32FirstW.argtypes = [HD, LP]; k.Process32FirstW.restype = BL
    k.Process32NextW.argtypes = [HD, LP]; k.Process32NextW.restype = BL
    k.CloseHandle.argtypes = [HD]; k.CloseHandle.restype = BL
    k.VirtualQueryEx.argtypes = [HD, LP, LP, ST]; k.VirtualQueryEx.restype = ST
    k.ReadProcessMemory.argtypes = [HD, LP, LP, ST, LP]; k.ReadProcessMemory.restype = BL
    k.WriteProcessMemory.argtypes = [HD, LP, LP, ST, LP]; k.WriteProcessMemory.restype = BL
    return k


def find_pid(k32, name="hoi4.exe"):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    pid = None
    while ok:
        if entry.szExeFile.lower() == name.lower():
            pid = entry.th32ProcessID
            break
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    return pid


def attach(write=False):
    k32 = _k32()
    pid = find_pid(k32)
    if not pid:
        sys.exit("hoi4.exe not found - is the game running?")
    access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    if write:
        access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
    h = k32.OpenProcess(access, False, pid)
    if not h:
        sys.exit(f"OpenProcess failed (err {ctypes.get_last_error()}) - run as Administrator.")
    log(f"attached pid={pid} write={write}")
    return k32, h, pid


def iter_regions(k32, h):
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    maxaddr = 0x7FFFFFFFFFFF
    sz = ctypes.sizeof(mbi)
    while addr < maxaddr:
        if k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), sz) != sz:
            break
        base = mbi.BaseAddress or 0
        region = mbi.RegionSize or 0
        if region == 0:
            break
        if (mbi.State == MEM_COMMIT and mbi.Protect in WRITABLE
                and not (mbi.Protect & PAGE_GUARD)):
            yield base, region, mbi.Protect
        addr = base + region


def read_bytes(k32, h, addr, size):
    buf = (ctypes.c_char * size)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    if not ok or got.value == 0:
        return None
    return bytes(buf[:got.value])


def scan(value, vtype):
    fmt, size = TYPES[vtype]
    packed = struct.pack(fmt, value)
    k32, h, _ = attach()
    t0 = time.time()
    cands, regions, scanned = [], 0, 0
    for base, rsize, _prot in iter_regions(k32, h):
        regions += 1
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            data = read_bytes(k32, h, base + off, n)
            if data:
                scanned += len(data)
                i = data.find(packed)
                while i >= 0:
                    cands.append(base + off + i)
                    i = data.find(packed, i + 1)
            if len(cands) > MAX_CANDS:
                break
            off += (n - (size - 1)) if n == CHUNK else n
        if len(cands) > MAX_CANDS:
            log(f"hit candidate cap {MAX_CANDS}; narrow with 'next' (value too common)")
            break
    cands = sorted(set(cands))
    CANDFILE.write_text(json.dumps({"type": vtype, "value": value, "addrs": cands}))
    log(f"SCANSUMMARY value={value} type={vtype} regions={regions} "
        f"scanned_mb={scanned // (1024 * 1024)} candidates={len(cands)} "
        f"elapsed={time.time() - t0:.1f}s")
    if len(cands) <= 12:
        for a in cands:
            log(f"  candidate 0x{a:X}")
    k32.CloseHandle(h)


def narrow(value):
    if not CANDFILE.is_file():
        sys.exit("no previous scan - run 'scan <value>' first.")
    prev = json.loads(CANDFILE.read_text())
    vtype = prev["type"]
    fmt, size = TYPES[vtype]
    packed = struct.pack(fmt, value)
    k32, h, _ = attach()
    kept = []
    for a in prev["addrs"]:
        data = read_bytes(k32, h, a, size)
        if data == packed:
            kept.append(a)
    CANDFILE.write_text(json.dumps({"type": vtype, "value": value, "addrs": kept}))
    log(f"NEXTSUMMARY value={value} type={vtype} before={len(prev['addrs'])} after={len(kept)}")
    if len(kept) <= 12:
        for a in kept:
            log(f"  candidate 0x{a:X}")
    k32.CloseHandle(h)


def range_scan(lo, hi):
    """Find every 4-aligned int32 in [lo, hi] - handles hidden decimals (a value
    shown as 37 but stored x1000 is really 37000-37999). Saves {addr:value} pairs."""
    k32, h, _ = attach()
    t0 = time.time()
    out = []
    for base, rsize, _p in iter_regions(k32, h):
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            d = read_bytes(k32, h, base + off, n)
            if d:
                arr = array.array("i")
                arr.frombytes(d[:len(d) // 4 * 4])
                out.extend([base + off + i * 4, v] for i, v in enumerate(arr) if lo <= v <= hi)
            off += n
            if len(out) > MAX_CANDS:
                log("range too common - hit cap; pick a more distinctive value")
                break
        if len(out) > MAX_CANDS:
            break
    RANGEFILE.write_text(json.dumps({"pairs": out}))
    log(f"RANGESCAN lo={lo} hi={hi} candidates={len(out)} elapsed={time.time() - t0:.1f}s")
    if len(out) <= 30:
        for a, v in sorted(out):
            log(f"  0x{a:X} = {v}")
    k32.CloseHandle(h)


def _load_range():
    return json.loads(RANGEFILE.read_text())["pairs"]


def range_op(op, lo=None, hi=None):
    """Narrow saved candidates: op 'between' (lo..hi) or 'up'/'down'/'same'/'changed'."""
    k32, h, _ = attach()
    out = []
    for a, ov in _load_range():
        d = read_bytes(k32, h, a, 4)
        if not d:
            continue
        v = struct.unpack("<i", d)[0]
        keep = ((op == "between" and lo <= v <= hi) or (op == "up" and v > ov)
                or (op == "down" and v < ov) or (op == "same" and v == ov)
                or (op == "changed" and v != ov))
        if keep:
            out.append([a, v])
    RANGEFILE.write_text(json.dumps({"pairs": out}))
    log(f"RANGE {op} lo={lo} hi={hi} -> {len(out)} candidates")
    if len(out) <= 30:
        for a, v in sorted(out):
            log(f"  0x{a:X} = {v}")
    k32.CloseHandle(h)


def range_peek():
    pairs = _load_range()
    print(f"{len(pairs)} candidates")
    for a, v in sorted(pairs)[:40]:
        print(f"  0x{a:X} = {v}")


def _capture(name):
    """Capture the HOI4 top bar to logs/watch/<name> via PowerShell (.NET)."""
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(ROOT / "tools" / "screencap.ps1"),
                        "-Out", str(SHOTDIR / name), "-H", "90"],
                       capture_output=True, timeout=20)
    except Exception as e:  # noqa: BLE001 - capture is best-effort
        log(f"capture failed: {e}")


def autofind(lo, hi, secs=25, maxmb=0):
    """Autonomous: seed a range scan, OBSERVE for `secs` while the game runs
    (capturing the screen itself), then keep only addresses whose value MOVED -
    the live values. No human in the loop, so no screenshot/scan lag. The agent
    labels the survivors from the captured screenshots afterwards.

    maxmb>0 skips regions larger than that (MB) to scan FAST - game-state heaps are
    small; the giant buffers it skips are textures/audio, so a fast-changing value
    barely drifts during a short scan."""
    SHOTDIR.mkdir(parents=True, exist_ok=True)
    cap = maxmb * 1024 * 1024
    k32, h, _ = attach()
    seed = {}
    t0 = time.time()
    for base, rsize, _p in iter_regions(k32, h):
        if cap and rsize > cap:
            continue
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            d = read_bytes(k32, h, base + off, n)
            if d:
                arr = array.array("i")
                arr.frombytes(d[:len(d) // 4 * 4])
                for i, v in enumerate(arr):
                    if lo <= v <= hi:
                        seed[base + off + i * 4] = v
            off += n
            if len(seed) > MAX_CANDS:
                break
        if len(seed) > MAX_CANDS:
            break
    log(f"AUTOFIND seed [{lo},{hi}] -> {len(seed)} in {time.time() - t0:.1f}s; observing {secs}s...")
    shots = max(2, secs // 4)
    for i in range(shots):
        _capture(f"af_{i:02d}.png")
        time.sleep(secs / shots)
    _capture("af_final.png")
    moved = {}
    for a, ov in seed.items():
        d = read_bytes(k32, h, a, 4)
        if not d:
            continue
        v = struct.unpack("<i", d)[0]
        if v != ov:
            moved[a] = [ov, v]
    RANGEFILE.write_text(json.dumps({"pairs": [[a, v] for a, (ov, v) in moved.items()]}))
    log(f"AUTOFIND moved -> {len(moved)} live candidates (value changed during observation):")
    for a, (ov, v) in sorted(moved.items())[:80]:
        log(f"  0x{a:X}  {ov} -> {v}")
    k32.CloseHandle(h)


def _ps(script, *args):
    return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-File", str(ROOT / "tools" / script), *args],
                          capture_output=True, timeout=30, text=True)


def _ocr_pp(x=190, w=130, tries=5):
    """Capture the bar, OCR just the Political Power digits. Retries transient
    misses (e.g. HOI4 momentarily not foreground). Returns int or None."""
    SHOTDIR.mkdir(parents=True, exist_ok=True)
    shot = SHOTDIR / "ac_bar.png"
    for _ in range(tries):
        _ps("screencap.ps1", "-Out", str(shot), "-H", "90")
        r = _ps("ocr.ps1", "-Path", str(shot), "-X", str(x), "-Y", "0", "-W", str(w), "-H", "90")
        txt = (r.stdout or "").strip().replace(",", "").upper()
        m = re.search(r"\d+", txt)
        if m and "K" not in txt:
            return int(m.group())
        time.sleep(0.6)
    return None


def autocheat(setval=None, mult=1000, iters=12):
    """Deterministic, NO AI in the loop: OCR Political Power, narrow memory to the
    addresses whose value matches PP x{mult}, repeat until one remains - then,
    if setval is given, write it. The program reads the number itself via OCR;
    the agent never reads a screenshot to drive this."""
    k32, h, _ = attach(write=(setval is not None))
    pp = _ocr_pp()
    if pp is None:
        log("AUTOCHEAT: OCR could not read PP"); k32.CloseHandle(h); return
    lo, hi = pp * mult, (pp + 12) * mult - 1   # wide: PP drifts during the seed scan
    log(f"AUTOCHEAT OCR PP={pp}; seed [{lo},{hi}] (skip >32MB regions)...")
    capmb = 32 * 1024 * 1024
    seed_cap = 4_000_000   # high, so PP is captured even in value-dense ranges
    cands = {}
    for base, rsize, _p in iter_regions(k32, h):
        if rsize > capmb:
            continue
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            d = read_bytes(k32, h, base + off, n)
            if d:
                arr = array.array("i")
                arr.frombytes(d[:len(d) // 4 * 4])
                for i, v in enumerate(arr):
                    if lo <= v <= hi:
                        cands[base + off + i * 4] = v
            off += n
            if len(cands) > seed_cap:
                break
        if len(cands) > seed_cap:
            break
    log(f"  seed -> {len(cands)} candidates")
    for it in range(iters):
        time.sleep(2.0)
        pp = _ocr_pp()
        if pp is None:
            continue
        lo, hi = pp * mult, (pp + 2) * mult - 1   # +2 tolerates 1 tick of lag in the read
        new = {}
        for a in cands:
            d = read_bytes(k32, h, a, 4)
            if d:
                v = struct.unpack("<i", d)[0]
                if lo <= v <= hi:
                    new[a] = v
        cands = new
        log(f"  iter {it}: OCR PP={pp} -> {len(cands)} candidates")
        if len(cands) <= 8:
            for a, v in sorted(cands.items()):
                log(f"    0x{a:X} = {v}")
        if len(cands) == 1:
            break
    json_pairs = [[a, v] for a, v in cands.items()]
    RANGEFILE.write_text(json.dumps({"pairs": json_pairs}))
    log(f"AUTOCHEAT result: {len(cands)} candidate(s) track Political Power")
    if setval is not None and len(cands) == 1:
        addr = next(iter(cands))
        w = ctypes.c_size_t(0)
        ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr),
                                    struct.pack("<i", setval * mult), 4, ctypes.byref(w))
        log(f"AUTOCHEAT WROTE 0x{addr:X} = {setval} (x{mult}) -> "
            f"{'OK' if ok and w.value == 4 else 'FAILED'}")
    k32.CloseHandle(h)


def read_addr(addr, vtype):
    fmt, size = TYPES[vtype]
    k32, h, _ = attach()
    data = read_bytes(k32, h, addr, size)
    if data is None or len(data) < size:
        log(f"READ 0x{addr:X} FAILED (err {ctypes.get_last_error()})")
    else:
        val = struct.unpack(fmt, data)[0]
        log(f"READ 0x{addr:X} {vtype}={val}")
    k32.CloseHandle(h)


def write_addr(addr, value, vtype):
    fmt, size = TYPES[vtype]
    packed = struct.pack(fmt, value)
    k32, h, _ = attach(write=True)
    written = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr),
                                packed, size, ctypes.byref(written))
    if ok and written.value == size:
        log(f"WROTE 0x{addr:X} {vtype}={value}")
    else:
        log(f"WRITE 0x{addr:X} FAILED (err {ctypes.get_last_error()})")
    k32.CloseHandle(h)


def info():
    k32, h, pid = attach()
    regions = total = 0
    for _b, rsize, _p in iter_regions(k32, h):
        regions += 1
        total += rsize
    log(f"INFO pid={pid} writable_regions={regions} writable_mb={total // (1024 * 1024)}")
    k32.CloseHandle(h)


def show_list():
    if not CANDFILE.is_file():
        print("no candidates yet - run 'scan <value>'")
        return
    d = json.loads(CANDFILE.read_text())
    print(f"{len(d['addrs'])} candidate(s), type={d['type']}, last value={d['value']}")
    for a in d["addrs"][:40]:
        print(f"  0x{a:X}")


def _int(s):
    return int(s, 0)  # accepts 0x... or decimal


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="attach and report writable region stats")
    sub.add_parser("list", help="show current candidate addresses")
    s = sub.add_parser("scan", help="first scan for a value")
    s.add_argument("value", type=_int); s.add_argument("--type", default="i32", choices=TYPES)
    n = sub.add_parser("next", help="narrow candidates to those now == value")
    n.add_argument("value", type=_int)
    r = sub.add_parser("read", help="read the value at an address")
    r.add_argument("addr", type=_int); r.add_argument("--type", default="i32", choices=TYPES)
    w = sub.add_parser("write", help="write a value to an address")
    w.add_argument("addr", type=_int); w.add_argument("value", type=_int)
    w.add_argument("--type", default="i32", choices=TYPES)
    rs = sub.add_parser("rangescan", help="range scan [lo,hi] (handles x1000 decimals)")
    rs.add_argument("lo", type=_int); rs.add_argument("hi", type=_int)
    rn = sub.add_parser("rangenext", help="narrow range candidates to [lo,hi]")
    rn.add_argument("lo", type=_int); rn.add_argument("hi", type=_int)
    sub.add_parser("rangeup", help="narrow range candidates to those that increased")
    sub.add_parser("rangedown", help="narrow range candidates to those that decreased")
    sub.add_parser("rangepeek", help="list current range candidates")
    af = sub.add_parser("autofind", help="seed [lo,hi], observe while playing, keep moved")
    af.add_argument("lo", type=_int); af.add_argument("hi", type=_int)
    af.add_argument("--secs", type=int, default=25)
    af.add_argument("--maxmb", type=int, default=0)
    ac = sub.add_parser("autocheat", help="OCR-driven, AI-free: find Political Power and optionally set it")
    ac.add_argument("--set", type=_int, default=None, dest="setval")
    ac.add_argument("--mult", type=int, default=1000)
    ac.add_argument("--iters", type=int, default=12)
    args = ap.parse_args()

    if args.cmd == "info":
        info()
    elif args.cmd == "list":
        show_list()
    elif args.cmd == "scan":
        scan(args.value, args.type)
    elif args.cmd == "next":
        narrow(args.value)
    elif args.cmd == "read":
        read_addr(args.addr, args.type)
    elif args.cmd == "write":
        write_addr(args.addr, args.value, args.type)
    elif args.cmd == "rangescan":
        range_scan(args.lo, args.hi)
    elif args.cmd == "rangenext":
        range_op("between", args.lo, args.hi)
    elif args.cmd == "rangeup":
        range_op("up")
    elif args.cmd == "rangedown":
        range_op("down")
    elif args.cmd == "rangepeek":
        range_peek()
    elif args.cmd == "autofind":
        autofind(args.lo, args.hi, args.secs, args.maxmb)
    elif args.cmd == "autocheat":
        autocheat(args.setval, args.mult, args.iters)


if __name__ == "__main__":
    main()
