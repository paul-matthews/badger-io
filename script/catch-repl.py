#!/usr/bin/env python3
"""
Catch the MicroPython REPL window on a Badger badge.

The badgeware firmware disables the interactive REPL once an app is running,
but there is a brief window (~300 ms) between MicroPython starting and the
app disabling USB CDC where Ctrl-C interrupts the boot sequence.

Usage:
  1. Run this script.
  2. Immediately press RESET on the device (or unplug/replug).
  3. If the window is caught, the script drops you into an mpremote shell.

Requires: pip install pyserial
"""
import glob
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial not installed — run: pip install pyserial")
    sys.exit(1)

PORT_PATTERN = "/dev/tty.usbmodem*"
BAUD = 115200
POLL_INTERVAL = 0.02   # 20 ms
WAIT_SECONDS = 90      # how long to wait for the device to appear
CTRL_C = b"\x03"


def find_port():
    ports = glob.glob(PORT_PATTERN)
    return ports[0] if ports else None


def try_interrupt(port):
    try:
        with serial.Serial(port, BAUD, timeout=0.3) as ser:
            # Double Ctrl-C — standard MicroPython interrupt sequence
            ser.write(CTRL_C + CTRL_C)
            time.sleep(0.15)
            # Send Enter to get a clean prompt
            ser.write(b"\r\n")
            time.sleep(0.15)
            response = ser.read(512)
            return response
    except Exception as e:
        return None


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
response = try_interrupt(port)

if response is None:
    print("Could not open port.")
    sys.exit(1)

print(f"Response: {repr(response)}")

if b">>>" in response or b"MicroPython" in response:
    print("\nREPL caught! Running: mpremote connect", port)
    import subprocess
    subprocess.run(["mpremote", "connect", port])
else:
    print("\nNo REPL prompt — the boot interrupt window was missed.")
    print("Try again: run this script, THEN press RESET within ~1 second.")
    print()
    print("If this consistently fails, the firmware may have the REPL disabled.")
    print("Alternative: use 'go run badger-push.go logs' to confirm the device")
    print("is reachable, then try the second device.")
