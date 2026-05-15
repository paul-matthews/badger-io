# Badger Badge Project

## Device
Pimoroni Badger 2350 W (RP2350). Google I/O 2026 conference badge.
Firmware: `github.com/pimoroni/badger2350` **v2.0.2** (2026-04-10). The device
was upgraded from the original v1.0.0 — all apps and API facts below target v2.0.2.

## Memory discipline
After any significant finding — an API quirk, a deploy technique, a device behaviour, a bug cause — save it to memory immediately using the Write tool at `~/.claude/projects/-Users-paulmatthews-src-Badger/memory/`. Update `MEMORY.md` index. Periodically prune stale or superseded entries. The goal is that a fresh context window can pick up exactly where the last one left off.

## Repo layout
- `apps/` — MicroPython apps deployed to `/system/apps/` on device
- `docs/` — GitHub Pages companion web app (url_share BLE page)
- `script/badger-push.go` — Go CLI for pushing code, data, logs, reset

## Toolchain
`badger-push` must be installed to `~/bin/` before use:
```bash
script/install.sh   # re-run whenever badger-push.go changes (build from the branch you deploy from)
```
All deploy commands below assume `badger-push` is on PATH.

## Deploy — device apps

## API reference
Full reference at `docs/badgeware-api-reference.md` — compiled from github.com/pimoroni/badgeware-docs.
Covers: screen/image API, badge hardware, color, shape, text, State, rtc, all fonts, SpriteSheet.

## Key API facts (pimoroni/badger2350 v2.0.2, 2026-04-10)
- **Display**: 264x176 pixels, e-paper, 4 shades of grey. `screen.width=264`, `screen.height=176`.
- **CRITICAL — App entry point**: `main.py` calls `launch(app)` which executes the app module. Apps
  call `run(update)` at **module level with NO `if __name__ == "__main__"` guard** — the guard
  prevents the app from ever starting. (This is the inverse of the retired v1.0.0 requirement.)
- `run(update)` is the event loop (watchdog, HOME-button exit). It does **NOT** auto-clear or
  auto-update the screen.
- `badge.update()` must be called from user code inside `update()`, and only when something was
  actually drawn — calling every frame causes constant e-paper refreshes.
- `badge.default_clear = None` — set at the top of `update()` every frame, else the framebuffer is
  cleared between frames and the screen goes blank. `badge` IS a global in v2.0.2.
- `wait_for_button_or_alarm()` — call at the end of every `update()`; pass `timeout=N` (ms) for
  periodic wakeups. Does NOT wake on a BLE IRQ.
- **Frozen globals (no import)**: `screen`, `badge`, `color`, `shape`, `image`, `rom_font`, `rect`,
  `vec2`, `mat3`, `brush`, `text`, `rtc`, `io` (may not exist), `wait_for_button_or_alarm`, `reset`,
  `launch`, `file_exists`, `BUTTON_A/B/C/UP/DOWN/HOME`.
- **Importable from badgeware**: `State` only — `run` is a plain global, NOT importable.
  Use `from badgeware import State`.
- **Buttons**: `badge.pressed(BUTTON_B)` — edge-triggered (true only on the first frame the button is
  down); `badge.held()` / `badge.released()` also exist. (Replaces the retired v1.0.0
  `io.BUTTON_B in io.pressed` pattern.)
- **Antialias**: `screen.antialias = screen.X2` — NOT `image.X2` (AttributeError on import).
- BLE GATT buffer must be pre-allocated: `_ble.gatts_write(handle, b'\x00' * size)` before use.
- Font renderer crashes on non-ASCII (em-dash etc) — ASCII only in all text.
- `screen` is of type `image` — does NOT support `set_rotation()` or similar runtime rotation.
- **Badger sleeps between updates** — module-level code / `init()` re-runs on every wake; persist
  state with `State.load`/`State.modify`.
- **`/system/` is read-only at runtime** — write app data to `/state/` (`State`, or raw file writes).

## Security / PII
- Real personal data lives in gitignored `*.local.json` only
- Never commit credentials, WiFi passwords, or real schedule data

## macOS deploy notes
- macOS 15 Sequoia blocks `cp` to FAT32 USB volumes — use `osascript` Finder or `mpremote fs cp`
- `mpremote fs cp` is the reliable deploy path when device is NOT in USB Disk Mode
