#!/usr/bin/env python3
"""
Catch the MicroPython REPL window on a Badger badge.

badgeware disables the interactive REPL once run() is called, but there is
a brief window (~300 ms) between MicroPython starting and the app disabling
USB where Ctrl-C can interrupt the boot sequence.

Usage:
  1. Run this script.
  2. Immediately press RESET on the device (or unplug/replug).
  3. If the window is caught, you get an interactive mpremote REPL.

No extra dependencies — uses mpremote, which is already installed.
"""
import glob
import subprocess
import sys
import time

PORT_PATTERN = "/dev/tty.usbmodem*"
POLL_INTERVAL = 0.02   # 20 ms — fast enough to catch the ~300 ms window
WAIT_SECONDS = 90


def find_port():
    ports = glob.glob(PORT_PATTERN)
    return ports[0] if ports else None


print(f"Waiting up to {WAIT_SECONDS}s for a serial port to appear...")
print("Press RESET on the device NOW.\n")

deadline = time.time() + WAIT_SECONDS
port = None

while time.time() < deadline:
    port = find_port()
    if port:
        break
    time.sleep(POLL_INTERVAL)

if not port:
    print("Timed out — no serial port found.")
    sys.exit(1)

print(f"Port appeared: {port}")
print(f"Running: mpremote connect {port}\n")

# mpremote automatically sends Ctrl-C twice before executing anything,
# which is the standard MicroPython boot interrupt sequence.
result = subprocess.run(["mpremote", "connect", port])

if result.returncode != 0:
    print("\nmpremote exited with an error.")
    print("The boot interrupt window was probably missed.")
    print("Try again: run this script, then press RESET within ~1 second.")
    print()
    print("If it consistently fails, the firmware may have REPL disabled at startup.")
