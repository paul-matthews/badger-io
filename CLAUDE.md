# Badger Badge Project

## Device
Pimoroni Badger 2350 W (RP2350). Google I/O 2026 conference badge.
Firmware: `bw-1.27.0, badger` — based on `badger/home` (github.com/badger/home) `mona-os-v4.03`.

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
2. Copy `github-badger-2350-with-filesystem.uf2` (from `badger/home` releases) to the volume
3. Device reboots automatically into original firmware + filesystem
4. Re-deploy custom apps with `badger-push`

UF2 URL: `https://github.com/badger/home/releases/download/mona-os-v4.03/github-badger-2350-with-filesystem.uf2`

## Key API facts (bw-1.27.0 firmware)
- `run(update_fn)` from badgeware is the app event loop. Handles `screen.update()`, watchdog, HOME button exit.
- `screen`, `io`, `color`, `shape`, `image`, `rom_font` are **frozen globals** — available after `import badgeware` but NOT as `badgeware.io` etc.
- `State`, `run` ARE importable: `from badgeware import run, State`
- `screen.update()` must NOT be called from user code — only `run()` calls it.
- `io.BUTTON_B in io.pressed` — button check pattern
- BLE GATT buffer must be pre-allocated: `_ble.gatts_write(handle, b'\x00' * 512)` before use
- Font renderer crashes on non-ASCII (em-dash etc) — ASCII only in all text

## Security / PII
- Real personal data lives in gitignored `*.local.json` only
- Never commit credentials, WiFi passwords, or real schedule data

## macOS deploy notes
- macOS 15 Sequoia blocks `cp` to FAT32 USB volumes — use `osascript` Finder or `mpremote fs cp`
- `mpremote fs cp` is the reliable deploy path when device is NOT in USB Disk Mode
