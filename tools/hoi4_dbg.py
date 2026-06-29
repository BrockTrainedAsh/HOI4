#!/usr/bin/env python3
"""
hoi4_dbg.py - "find out what accesses this address" for HOI4, via hardware
breakpoints (Windows debug registers). This is the proven trainer method: when the
game's code reads/writes the address, we catch the debug event and dump the CPU
registers. Whichever register equals (address - small offset) IS the struct pointer
(pPlayer / a sub-object) and reveals the real offset on THIS game version. No
disassembler, no code injection - once we know pPlayer + offsets, hoi4_mem reads and
writes the real values.

    python hoi4_dbg.py trace 0x26D95A01E38            # find what ACCESSES (read/write)
    python hoi4_dbg.py trace 0x... --write --secs 8   # only writes, watch 8s

SAFETY: this attaches a debugger to the live game. We set kill-on-exit FALSE (detach
won't close HOI4), always detach in a finally, and bound the run by --secs/--hits.
Save your game before running. Read-only: it observes, it does not modify anything.
"""
import argparse
import ctypes as C
import sys
import time
from ctypes import wintypes

if sys.platform != "win32":
    sys.exit("Run with Windows Python.")

k = C.WinDLL("kernel32", use_last_error=True)

# ---- constants -----------------------------------------------------------
TH32CS_SNAPTHREAD = 0x04
THREAD_ALL = 0x1FFFFF
CONTEXT_AMD64 = 0x00100000
CONTEXT_CONTROL = CONTEXT_AMD64 | 0x1
CONTEXT_INTEGER = CONTEXT_AMD64 | 0x2
CONTEXT_DEBUG = CONTEXT_AMD64 | 0x10
CONTEXT_FULL = CONTEXT_CONTROL | CONTEXT_INTEGER | (CONTEXT_AMD64 | 0x8)
EXCEPTION_DEBUG_EVENT = 1
CREATE_THREAD_DEBUG_EVENT = 2
EXIT_PROCESS_DEBUG_EVENT = 5
EXCEPTION_SINGLE_STEP = 0x80000004
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001


# ---- structures ----------------------------------------------------------
class THREADENTRY32(C.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD)]


class M128A(C.Structure):
    _fields_ = [("Low", C.c_ulonglong), ("High", C.c_longlong)]


class CONTEXT(C.Structure):
    _pack_ = 16
    _fields_ = [
        ("P1Home", C.c_ulonglong), ("P2Home", C.c_ulonglong), ("P3Home", C.c_ulonglong),
        ("P4Home", C.c_ulonglong), ("P5Home", C.c_ulonglong), ("P6Home", C.c_ulonglong),
        ("ContextFlags", wintypes.DWORD), ("MxCsr", wintypes.DWORD),
        ("SegCs", wintypes.WORD), ("SegDs", wintypes.WORD), ("SegEs", wintypes.WORD),
        ("SegFs", wintypes.WORD), ("SegGs", wintypes.WORD), ("SegSs", wintypes.WORD),
        ("EFlags", wintypes.DWORD),
        ("Dr0", C.c_ulonglong), ("Dr1", C.c_ulonglong), ("Dr2", C.c_ulonglong),
        ("Dr3", C.c_ulonglong), ("Dr6", C.c_ulonglong), ("Dr7", C.c_ulonglong),
        ("Rax", C.c_ulonglong), ("Rcx", C.c_ulonglong), ("Rdx", C.c_ulonglong),
        ("Rbx", C.c_ulonglong), ("Rsp", C.c_ulonglong), ("Rbp", C.c_ulonglong),
        ("Rsi", C.c_ulonglong), ("Rdi", C.c_ulonglong), ("R8", C.c_ulonglong),
        ("R9", C.c_ulonglong), ("R10", C.c_ulonglong), ("R11", C.c_ulonglong),
        ("R12", C.c_ulonglong), ("R13", C.c_ulonglong), ("R14", C.c_ulonglong),
        ("R15", C.c_ulonglong), ("Rip", C.c_ulonglong),
        ("FltSave", C.c_byte * 512),
        ("VectorRegister", M128A * 26), ("VectorControl", C.c_ulonglong),
        ("DebugControl", C.c_ulonglong), ("LastBranchToRip", C.c_ulonglong),
        ("LastBranchFromRip", C.c_ulonglong), ("LastExceptionToRip", C.c_ulonglong),
        ("LastExceptionFromRip", C.c_ulonglong),
    ]


class EXCEPTION_RECORD(C.Structure):
    _fields_ = [("ExceptionCode", wintypes.DWORD), ("ExceptionFlags", wintypes.DWORD),
                ("ExceptionRecord", C.c_void_p), ("ExceptionAddress", C.c_void_p),
                ("NumberParameters", wintypes.DWORD), ("_pad", wintypes.DWORD),
                ("ExceptionInformation", C.c_ulonglong * 15)]


class EXCEPTION_DEBUG_INFO(C.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", wintypes.DWORD)]


class DEBUG_EVENT(C.Structure):
    # u is approximated by its largest member (EXCEPTION_DEBUG_INFO); big enough buffer.
    _fields_ = [("dwDebugEventCode", wintypes.DWORD), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD), ("u", EXCEPTION_DEBUG_INFO),
                ("_tail", C.c_byte * 64)]


for _f, _a, _r in (
    ("OpenThread", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], C.c_void_p),
    ("SuspendThread", [C.c_void_p], wintypes.DWORD),
    ("ResumeThread", [C.c_void_p], wintypes.DWORD),
    ("GetThreadContext", [C.c_void_p, C.c_void_p], wintypes.BOOL),
    ("SetThreadContext", [C.c_void_p, C.c_void_p], wintypes.BOOL),
    ("CloseHandle", [C.c_void_p], wintypes.BOOL),
    ("DebugActiveProcess", [wintypes.DWORD], wintypes.BOOL),
    ("DebugActiveProcessStop", [wintypes.DWORD], wintypes.BOOL),
    ("DebugSetProcessKillOnExit", [wintypes.BOOL], wintypes.BOOL),
    ("WaitForDebugEvent", [C.c_void_p, wintypes.DWORD], wintypes.BOOL),
    ("ContinueDebugEvent", [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD], wintypes.BOOL),
    ("CreateToolhelp32Snapshot", [wintypes.DWORD, wintypes.DWORD], C.c_void_p),
    ("Thread32First", [C.c_void_p, C.c_void_p], wintypes.BOOL),
    ("Thread32Next", [C.c_void_p, C.c_void_p], wintypes.BOOL),
):
    getattr(k, _f).argtypes = _a
    getattr(k, _f).restype = _r


def find_pid(name="hoi4.exe"):
    from subprocess import check_output
    out = check_output(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                       text=True, errors="replace")
    for line in out.splitlines():
        if name.lower() in line.lower():
            return int(line.split(",")[1].strip().strip('"'))
    return None


def threads(pid):
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32(); te.dwSize = C.sizeof(te)
    out = []
    if k.Thread32First(snap, C.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                out.append(te.th32ThreadID)
            if not k.Thread32Next(snap, C.byref(te)):
                break
    k.CloseHandle(snap)
    return out


def dr7_for(rw, length=3):
    # L0 enable + R/W0 (01=write, 11=access) + LEN0 (11=4 bytes)
    return 0x1 | (rw << 16) | (length << 18)


def set_bp(tid, addr, dr7):
    th = k.OpenThread(THREAD_ALL, False, tid)
    if not th:
        return
    k.SuspendThread(th)
    ctx = CONTEXT(); ctx.ContextFlags = CONTEXT_DEBUG
    if k.GetThreadContext(th, C.byref(ctx)):
        ctx.Dr0 = addr
        ctx.Dr7 = dr7
        ctx.ContextFlags = CONTEXT_DEBUG
        k.SetThreadContext(th, C.byref(ctx))
    k.ResumeThread(th)
    k.CloseHandle(th)


GPR = ("Rax", "Rcx", "Rdx", "Rbx", "Rsp", "Rbp", "Rsi", "Rdi",
       "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15")


def trace(addr, rw, secs, max_hits):
    pid = find_pid()
    if not pid:
        print("hoi4.exe not running"); return
    print(f"[dbg] attaching to pid {pid}; watching 0x{addr:X} for "
          f"{'writes' if rw == 1 else 'read/write'} ({secs}s, <= {max_hits} hits)")
    if not k.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed (err {C.get_last_error()})"); return
    k.DebugSetProcessKillOnExit(False)
    dr7 = dr7_for(rw)
    hits, seen = [], set()
    evt = DEBUG_EVENT()
    deadline = time.time() + secs
    try:
        for tid in threads(pid):
            set_bp(tid, addr, dr7)
        while time.time() < deadline and len(hits) < max_hits:
            if not k.WaitForDebugEvent(C.byref(evt), 200):
                continue
            status = DBG_CONTINUE
            code = evt.dwDebugEventCode
            if code == EXIT_PROCESS_DEBUG_EVENT:
                break
            if code == CREATE_THREAD_DEBUG_EVENT:
                set_bp(evt.dwThreadId, addr, dr7)
            elif code == EXCEPTION_DEBUG_EVENT:
                if evt.u.ExceptionRecord.ExceptionCode == EXCEPTION_SINGLE_STEP:
                    th = k.OpenThread(THREAD_ALL, False, evt.dwThreadId)
                    ctx = CONTEXT(); ctx.ContextFlags = CONTEXT_FULL | CONTEXT_DEBUG
                    if th and k.GetThreadContext(th, C.byref(ctx)):
                        rip = ctx.Rip
                        if rip not in seen:
                            seen.add(rip)
                            regs = {n: getattr(ctx, n) for n in GPR}
                            # which register is the struct base?  addr = [reg + offset]
                            bases = [(n, addr - v) for n, v in regs.items()
                                     if 0 <= addr - v <= 0x6000]
                            hits.append((rip, regs, bases))
                            tag = ", ".join(f"{n}+0x{off:X}" for n, off in bases) or "?"
                            print(f"[hit] RIP=0x{rip:X}  base candidates: {tag}")
                    if th:
                        k.CloseHandle(th)
                else:
                    status = DBG_EXCEPTION_NOT_HANDLED
            k.ContinueDebugEvent(evt.dwProcessId, evt.dwThreadId, status)
    finally:
        for tid in threads(pid):
            set_bp(tid, 0, 0)
        k.DebugActiveProcessStop(pid)
        print(f"[dbg] detached. {len(hits)} distinct instruction(s) touched 0x{addr:X}.")
    # summary: the most common base register/offset is the struct pointer
    from collections import Counter
    cnt = Counter()
    for _rip, _regs, bases in hits:
        for n, off in bases:
            cnt[(n, off)] += 1
    if cnt:
        print("[dbg] base pointer candidates (register = pPlayer/sub-object, +offset):")
        for (n, off), c in cnt.most_common(8):
            base_val = next(r[n] for _rip, r, _b in hits if n in r)
            print(f"    {n} = 0x{base_val:X}  ->  0x{addr:X} = [{n} + 0x{off:X}]   (x{c})")


def selftest(secs=4):
    """Attach, pump/continue all debug events (NO breakpoint), detach. Proves the
    risky machinery is safe before we trace anything real."""
    pid = find_pid()
    if not pid:
        print("hoi4.exe not running"); return
    print(f"[selftest] attaching to pid {pid} for {secs}s (no breakpoint set)...")
    if not k.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed (err {C.get_last_error()})"); return
    k.DebugSetProcessKillOnExit(False)
    evt = DEBUG_EVENT()
    deadline = time.time() + secs
    n = 0
    try:
        while time.time() < deadline:
            if k.WaitForDebugEvent(C.byref(evt), 200):
                n += 1
                if evt.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT:
                    break
                k.ContinueDebugEvent(evt.dwProcessId, evt.dwThreadId, DBG_CONTINUE)
    finally:
        ok = k.DebugActiveProcessStop(pid)
        print(f"[selftest] pumped {n} events; detached cleanly={bool(ok)}. Game should be alive.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace", help="find what accesses an address")
    t.add_argument("addr", type=lambda s: int(s, 0))
    t.add_argument("--write", action="store_true", help="only writes (else read+write)")
    t.add_argument("--secs", type=int, default=8)
    t.add_argument("--hits", type=int, default=12)
    st = sub.add_parser("selftest", help="attach/detach safely, no breakpoint")
    st.add_argument("--secs", type=int, default=4)
    a = ap.parse_args()
    if a.cmd == "trace":
        trace(a.addr, 1 if a.write else 3, a.secs, a.hits)
    elif a.cmd == "selftest":
        selftest(a.secs)


if __name__ == "__main__":
    main()
