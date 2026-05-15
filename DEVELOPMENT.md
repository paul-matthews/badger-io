# Development Guide

Living document. Append new issues and resolutions as they arise; do not rewrite history.

## Toolchain setup

**Prerequisites**
- Go 1.21+
- Python 3 (`python3 -m http.server`)
- `mpremote` — `pip install mpremote`
- Chrome or Edge (Web Bluetooth requires a secure context; use these browsers for `badger-push docs`)

**Install badger-push**

Run once after cloning, and again whenever `script/badger-push.go` changes on `main`:

```bash
script/install.sh
```

This compiles the binary and installs it to `~/bin/badger-push`. Make sure `~/bin` is on your `PATH`. All commands below assume `badger-push` is on PATH; if not, substitute `go run script/badger-push.go`.

---

## Multi-agent development model

Multiple Claude Code agents can work on different apps simultaneously, each in its own git worktree. Each agent owns one app and deploys only that app to the device, leaving others intact.

### Starting a feature

```bash
# Claude Code will create the worktree automatically when you use the worktree skill,
# or you can create it manually:
git worktree add .claude/worktrees/my-feature -b worktree-my-feature
```

### Per-app deploy (non-destructive)

From any worktree or the main repo:

```bash
badger-push upload url_share        # push only url_share — other apps on device untouched
badger-push upload card             # push only card
badger-push upload url_share card   # push two apps
badger-push data url_share          # push only url_share JSON (no .py/.png re-upload)
```

The device retains whatever other apps were previously deployed. An agent working on `card` can push its changes without affecting the `url_share` state you just tested.

### Full deploy (from main only)

```bash
badger-push upload                  # push all apps — use when you want a clean device state
badger-push disk                    # full deploy via USB Disk Mode (all apps, no filtering)
```

Full deploy from `main` is the canonical reset — use it when the device has drifted or after merging multiple feature branches.

---

## Deploy reference

| Command | What it does |
|---|---|
| `badger-push upload [APP...]` | Push app code via mpremote. No APPs = all apps. |
| `badger-push data [APP...]` | Push JSON data files only. No APPs = all apps. |
| `badger-push disk` | Full deploy all apps via USB Disk Mode (Finder/osascript). |
| `badger-push docs` | Serve `docs/` on `localhost:8080` for BLE testing. |
| `badger-push logs` | Tail serial output from device. |
| `badger-push reset` | Soft-reset the device. |
| `badger-push flash <file.uf2>` | Flash firmware via BOOTSEL mode. |

Global flags: `--port`, `--dry-run`, `--yes`, `-v / -vv`.

---

## Web companion (docs/)

`docs/index.html` is the BLE URL Share companion page, served via GitHub Pages at the repo's Pages URL.

**Local testing:**

```bash
badger-push docs
# → http://localhost:8080
```

Web Bluetooth only works in Chrome/Edge and requires `localhost` (not `file://`). The `badger-push docs` command handles this.

**Deploy to production:**

```bash
git push origin main
```

GitHub Pages auto-deploys from `main`. There is no separate deploy step. Docs changes go live only after merging to `main` — test locally first.

**If docs/ grows to multiple pages**, organise by app:
```
docs/
  url_share/index.html
  shared.css
```
Each page lives at `<pages-url>/<app>/`.

---

## Device recovery (factory reset)

1. Hold BOOTSEL button while plugging in USB → device mounts as **RP2350**
2. `badger-push flash path/to/github-badger-2350-with-filesystem.uf2`
3. Device reboots automatically into original firmware + filesystem
4. Re-deploy custom apps: `badger-push upload`

UF2 source: `https://github.com/badger/home/releases/tag/mona-os-v4.03`

---

## Known issues log

<!-- Append new entries below. Format: ### YYYY-MM-DD: Title -->

### 2026-05-15: macOS 15 Sequoia blocks shell `cp` to FAT32 volumes

**Symptom:** `cp` or Go `os.WriteFile` to `/Volumes/BADGER` fails silently or with a permissions error on macOS 15.

**Cause:** FSKit entitlement changes in Sequoia mean only processes with the correct entitlements (i.e. Finder) can write to FAT32 volumes via the shell.

**Resolution:** Use `osascript` to drive Finder for all disk-mode copies. The `badger-push disk` command does this automatically. For mpremote-based deploys (`badger-push upload`), no workaround needed — mpremote talks over the REPL, not the filesystem.

---

### 2026-05-15: Font renderer crashes on non-ASCII characters

**Symptom:** Device crashes or displays garbage when text contains em-dashes, smart quotes, or any non-ASCII character.

**Cause:** The Badgeware `rom_font` renderer is ASCII-only.

**Resolution:** All strings passed to the display must be ASCII. Replace em-dashes with `--`, strip smart quotes, etc.

---

### 2026-05-15: `file://` URL does not work for Web Bluetooth testing

**Symptom:** Opening `docs/index.html` directly in the browser loads the page but Web Bluetooth is unavailable (`navigator.bluetooth` is undefined).

**Cause:** Web Bluetooth requires a secure context. `file://` URLs are not considered secure contexts by Chrome/Edge.

**Resolution:** Use `badger-push docs` to serve on `localhost:8080`, which is a secure context.

---

### 2026-05-15: BLE GATT write fails if buffer not pre-allocated

**Symptom:** `_ble.gatts_write()` raises an error or silently drops data on the MicroPython side.

**Cause:** The GATT characteristic buffer must be sized before first use.

**Resolution:** Pre-allocate with `_ble.gatts_write(handle, b'\x00' * 512)` during BLE setup, before any real writes.
