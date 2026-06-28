#!/usr/bin/env python3
"""
hoi4_console.py - run a HOI4 console command by focusing the game and simulating
keystrokes (Windows). This is the PROVEN way to change calculated values like
Political Power/Manpower: the game's own code applies them. The agent verifies the
effect with OCR; this just sends the command.

    python hoi4_console.py "add_political_power 5000"

Keys are held ~60ms each (HOI4 polls the keyboard per frame; a too-short tap is
missed). If the console does not open, change GRAVE to your layout's console key.
"""
import ctypes
import sys
import time

if sys.platform != "win32":
    sys.exit("Run with Windows Python.")

u = ctypes.WinDLL("user32", use_last_error=True)
u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
u.EnumWindows.argtypes = [_ENUMPROC, ctypes.c_void_p]

GRAVE, ENTER, SHIFT = 0xC0, 0x0D, 0x10
HOLD, GAP = 0.06, 0.04
VK = {" ": 0x20, ".": 0xBE, "-": 0xBD, "/": 0xBF}
for _i in range(26):
    VK[chr(97 + _i)] = 0x41 + _i
for _i in range(10):
    VK[chr(48 + _i)] = 0x30 + _i
SHIFTED = {"_": 0xBD}
KEYUP = 0x0002
SCANCODE = 0x0008
GRAVE_SCAN = 0x29   # physical scancode of the ` / ~ key (HOI4 reads the console key by scancode)


def _key(vk, down):
    u.keybd_event(vk, 0, 0 if down else KEYUP, 0)


def tap(vk):
    _key(vk, True); time.sleep(HOLD); _key(vk, False); time.sleep(GAP)


def tap_scan(scan):
    """Tap a key by physical scancode (more reliable for the HOI4 console key)."""
    u.keybd_event(0, scan, SCANCODE, 0); time.sleep(HOLD)
    u.keybd_event(0, scan, SCANCODE | KEYUP, 0); time.sleep(GAP)


def typ(s):
    for c in s.lower():
        if c in SHIFTED:
            _key(SHIFT, True); time.sleep(GAP)
            tap(SHIFTED[c])
            _key(SHIFT, False); time.sleep(GAP)
        elif c in VK:
            tap(VK[c])


def focus_hoi4():
    found = []

    def _cb(hwnd, _lp):
        ln = u.GetWindowTextLengthW(hwnd)
        if ln:
            buf = ctypes.create_unicode_buffer(ln + 1)
            u.GetWindowTextW(hwnd, buf, ln + 1)
            if "Hearts of Iron" in buf.value:
                found.append(hwnd)
        return True

    u.EnumWindows(_ENUMPROC(_cb), None)
    if found:
        u.SetForegroundWindow(ctypes.c_void_p(found[0]))
        time.sleep(0.6)
        return True
    return False


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: hoi4_console.py "add_political_power 5000"')
    cmd = sys.argv[1]
    if not focus_hoi4():
        sys.exit("Hearts of Iron IV window not found")
    time.sleep(0.4)
    tap_scan(GRAVE_SCAN)           # open console by physical scancode
    if cmd.upper() == "OPEN":      # safe test: just toggle the console, type nothing
        print("toggled console via scancode - check the game"); return
    time.sleep(0.3)
    typ(cmd); time.sleep(0.15)
    tap(ENTER); time.sleep(0.15)   # execute
    tap_scan(GRAVE_SCAN)           # close console
    print("sent:", cmd)


if __name__ == "__main__":
    main()
