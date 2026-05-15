# Badger Badge Project

## Device
Pimoroni Badger 2350 W (RP2350). Google I/O 2026 conference badge.
Firmware: `bw-1.27.0` — from `github.com/pimoroni/badger2350` v1.0.0 (2026-01-28).

## Memory discipline
After any significant finding — an API quirk, a deploy technique, a device behaviour, a bug cause — save it to memory immediately using the Write tool at `~/.claude/projects/-Users-paulmatthews-src-Badger/memory/`. Update `MEMORY.md` index. Periodically prune stale or superseded entries. The goal is that a fresh context window can pick up exactly where the last one left off.

## Repo layout
- `apps/` — MicroPython apps deployed to `/system/apps/` on device
- `docs/` — GitHub Pages companion web app (url_share BLE page)
- `script/badger-push.go` — Go CLI for pushing code, data, logs, reset

## Deploy
```bash
cd script && go run badger-push.go          # upload apps/
cd script && go run badger-push.go data     # push JSON state only
cd script && go run badger-push.go logs     # tail serial
cd script && go run badger-push.go reset    # soft reset
```
`docs/` is served via GitHub Pages — push to origin to deploy.

## Device recovery (factory reset)
1. Hold BOOTSEL button while plugging in USB → device mounts as **RP2350**
2. Copy the v1.0.0 UF2 to the volume
3. Device reboots automatically into original firmware + filesystem
4. Re-deploy custom apps with `badger-push disk`

UF2 URL: `https://github.com/pimoroni/badger2350/releases/download/v1.0.0/pimoroni-badger2350w-v1.0.0-micropython.uf2`

## API reference
Full reference at `docs/badgeware-api-reference.md` — compiled from github.com/pimoroni/badgeware-docs.
Covers: screen/image API, badge hardware, color, shape, text, State, rtc, all fonts, SpriteSheet.

## Key API facts (bw-1.27.0 / pimoroni/badger2350 v1.0.0)
- **Display**: 264x176 pixels, e-paper, 4 shades of grey. `screen.width=264`, `screen.height=176`.
- **CRITICAL — App entry point**: v1.0.0 `/system/main.py` does `running_app = __import__(app)` then
  calls `run(running_app.update)` itself. Apps MUST use `if __name__ == "__main__": run(update)` guard
  so `run()` is NOT triggered during import. Without the guard, `run()` blocks inside `__import__()`,
  `running_app` is never assigned, and HOME fires `NameError: name 'running_app' isn't defined`.
- `run(update_fn)` from badgeware is the app event loop. Handles `screen.update()`, watchdog, HOME button exit.
- `screen`, `badge`, `color`, `shape`, `image`, `rom_font`, `rect`, `vec2`, `mat3`, `brush`, `text`, `State`, `rtc`
  are **frozen globals / builtins** — available everywhere, NOT as `badgeware.screen` etc.
- `State`, `run` ARE importable: `from badgeware import run, State`
- `screen.update()` must NOT be called from user code — only `run()` calls it.
- **Button pattern (v1.0.0)**: `io.BUTTON_B in io.pressed` — `badge.pressed()` API is for newer firmware
  Constants: `BUTTON_A`, `BUTTON_B`, `BUTTON_C`, `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_HOME`
- BLE GATT buffer must be pre-allocated: `_ble.gatts_write(handle, b'\x00' * 512)` before use
- Font renderer crashes on non-ASCII (em-dash etc) — ASCII only in all text
- `screen` is of type `image` — does NOT support `set_rotation()` or similar runtime rotation
- **Badger sleeps between updates** — `init()` re-runs on every wake; save state with `State.save/load`

## Security / PII
- Real personal data lives in gitignored `*.local.json` only
- Never commit credentials, WiFi passwords, or real schedule data

## macOS deploy notes
- macOS 15 Sequoia blocks `cp` to FAT32 USB volumes — use `osascript` Finder or `mpremote fs cp`
- `mpremote fs cp` is the reliable deploy path when device is NOT in USB Disk Mode
