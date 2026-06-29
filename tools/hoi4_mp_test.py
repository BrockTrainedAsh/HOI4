#!/usr/bin/env python3
"""Test whether manpower is a directly-writable count: scan int+double at the displayed
value, freeze them all to 99,000,000 briefly, capture the bar mid-freeze, restore.
    python hoi4_mp_test.py 386700 386720
"""
import array
import struct
import subprocess
import sys
import time

sys.path.insert(0, "tools")
import hoi4_mem as M  # noqa: E402

WIN = r"C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit"


def main():
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    k, h, _ = M.attach(write=True)
    ints, dbls = [], []
    for base, rsize, _p in M.iter_regions(k, h):
        if rsize > 64 * 1024 * 1024:
            continue
        off = 0
        while off < rsize:
            n = min(M.CHUNK, rsize - off)
            d = M.read_bytes(k, h, base + off, n)
            if d:
                ia = array.array("i"); ia.frombytes(d[:len(d) // 4 * 4])
                for i, v in enumerate(ia):
                    if lo <= v <= hi:
                        ints.append(base + off + i * 4)
                da = array.array("d"); da.frombytes(d[:len(d) // 8 * 8])
                for i, v in enumerate(da):
                    if lo <= v <= hi:
                        dbls.append(base + off + i * 8)
            off += n
    M.log(f"mp_test: {len(ints)} int, {len(dbls)} double candidates at [{lo},{hi}]")
    oi = [(a, M.read_bytes(k, h, a, 4)) for a in ints]
    od = [(a, M.read_bytes(k, h, a, 8)) for a in dbls]
    pi = struct.pack("<i", 99000000)
    pd = struct.pack("<d", 99000000.0)
    w = M.ctypes.c_size_t(0)
    end = time.time() + 5
    shot = False
    while time.time() < end:
        for a in ints:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), pi, 4, M.ctypes.byref(w))
        for a in dbls:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), pd, 8, M.ctypes.byref(w))
        if not shot and time.time() > end - 3:
            subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", WIN + r"\tools\screencap.ps1",
                            "-Out", WIN + r"\logs\watch\mp_frozen.png", "-H", "70"],
                           capture_output=True)
            shot = True
    for a, o in oi:
        if o:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), o, 4, M.ctypes.byref(w))
    for a, o in od:
        if o:
            k.WriteProcessMemory(h, M.ctypes.c_void_p(a), o, 8, M.ctypes.byref(w))
    M.log("mp_test: captured mid-freeze + restored")
    k.CloseHandle(h)


if __name__ == "__main__":
    main()
