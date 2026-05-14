# Badger 2350 — Pre-Installed Capability Briefing

**Device:** Pimoroni Badger 2350  
**Firmware:** BadgeOS v4.03 (MicroPython)  
**Source:** Physical inspection of `/Volumes/BADGER` + GitHub `pimoroni/badger2040`  
**Date:** 2026-05-14

---

## Hardware Specs

| Feature | Detail |
|---|---|
| Display | 2.9" e-ink, 296×128px, monochrome + dithering (16 grey levels) |
| Processor | RP2350 (successor to RP2040) |
| WiFi | Yes (built-in, credentials in `secrets.py`) |
| RTC | Yes — PCF85063A, supports alarm-triggered wake |
| Buttons | A, B, C (main actions) + UP / DOWN (navigation) |
| USB | Mass storage mode via dedicated app |
| Battery | Monitored; charging status shown in menu |
| Flash | Internal filesystem visible at `/Volumes/BADGER` |

**Display note:** E-ink refreshes slowly — avoid animations requiring fast updates. Partial updates (`partial_update(x, y, w, h)`) are possible but dimensions must be multiples of 8px.

---

## Pre-Installed Apps (on the physical device)

The Badger 2350 ships with **6 apps**, distinct from the older 2040 set.

### 1. Badge — Personal ID Card
**File:** `apps/badge/__init__.py`  
Displays a customisable identity card: photo (avatar.png), name, role, and up to 4 social handles. Supports 42 social media platform icons (GitHub, Discord, Bluesky, Mastodon, LinkedIn, Instagram, etc.).

- **Button B:** Flip to social handles view
- **UP/DOWN:** Adjust background dither pattern
- **Configurable:** Name, role, socials hardcoded in the file

**Capability relevance:** Ready-made personal badge with social icons. Edit `apps/badge/__init__.py` directly to customise identity. Photo goes in `apps/badge/avatar.png`.

---

### 2. Clock — Multi-Style Time Display
**Files:** `apps/clock/__init__.py`, `daylightsaving.py`, `usermessage.py`  
Four visual clock styles: text, dot matrix, scribble (hand-drawn aesthetic), 7-segment digital. Syncs via NTP over WiFi. DST support for 9 world regions. RTC alarm wakes device at each minute boundary.

- **Button B:** Force NTP WiFi sync
- **A/C:** Cycle through clock styles
- **UP/DOWN:** Toggle dark/light mode
- **`secrets.py`:** Set `REGION` and `TIMEZONE` for correct local time

**Capability relevance:** Full real-time clock with WiFi sync. If you need timestamping, scheduling, or time display — it's done.

---

### 3. Hydrate — Water Intake Tracker
**File:** `apps/hydrate/__init__.py`  
Tracks daily water intake toward a 2,000ml goal. Visualised as a pie-chart progress ring. Celebrates goal completion with a gold star. State persists between sessions.

- **Button B:** Open adjustment menu
- **A/C:** Increase/decrease amount (100ml steps)
- **DOWN:** Confirm

**Capability relevance:** Example of persistent numeric tracking with graphical display. Reusable pattern for any "track progress toward a goal" feature.

---

### 4. Mass Storage — USB File Transfer Mode
**File:** `apps/mass_storage/__init__.py`  
Activates USB mass storage so the device appears as a drive (i.e., `/Volumes/BADGER`). Exits back to the menu.

**Capability relevance:** This is how you copy files to/from the device without a serial connection.

---

### 5. Menu — App Launcher
**Files:** `apps/menu/__init__.py`, `app.py`, `ui.py`  
Auto-discovers all apps in the apps directory. Displays a 3×2 icon grid with pagination. Shows battery level and BadgeOS version in the header.

- **A/C:** Navigate left/right
- **UP/DOWN:** Navigate rows
- **Button B:** Launch selected app

**Capability relevance:** Any new app you drop into `apps/yourapp/__init__.py` with an `icon.png` is automatically discovered and launchable.

---

### 6. The Compendium — 3D Dungeon-Crawler Game
**Files:** `apps/the_compendium/` (8 Python modules)  
A full first-person 3D raycasting game with 5 levels, 4 NPCs with 80+ dialogue nodes, quest/inventory system, and cutscenes. Technically impressive for an e-ink badge.

**Capability relevance:** The raycaster (`raycaster.py`) and dialogue system (`dialogue.py`) are reusable components if you need first-person navigation or branching conversation trees. Also proves the hardware can handle real-time raycasting — performance ceiling is higher than expected.

---

## Asset Library

### Fonts (35 files in `assets/fonts/`)
Mix of Pimoroni Punyfont (`.ppf`) and Adobe Font (`.af`) formats. Notable options:

| Style | Fonts |
|---|---|
| Clean/readable | `smart`, `memo`, `compassion`, `ignore` |
| Decorative | `bacteria`, `holotype`, `treasure`, `kobold`, `nope` |
| Stylised | `fear`, `loser`, `sins`, `troll`, `curse` |
| Standard | `DynaPuff-Medium.af`, `IndieFlower-Regular.af`, `MonaSans-Medium.af` |
| Icon | `awesome` (symbols for button hints) |

### Image Assets
- **Mona Sprites** (8 variants): `default`, `code`, `dance`, `eating`, `heart`, `love`, `dead`, `notify`
- **Social Icons** (42 platforms): in `apps/badge/assets/socials/`
- **System icons:** `assets/icons.png`
- **Game graphics:** 16 PNGs in `apps/the_compendium/assets/`

---

## Key APIs (MicroPython / BadgeOS)

### Display
```python
badger.set_pen(0-15)            # 0=black, 15=white, 1-14=dithered grey
badger.clear()
badger.update()                  # Full e-ink refresh
badger.partial_update(x, y, w, h)  # Partial refresh (w/h must be multiples of 8)
badger.set_update_speed(speed)   # NORMAL / MEDIUM / FAST / TURBO
```

### Text & Graphics
```python
badger.set_font("font_name")
badger.set_thickness(n)          # For Hershey vector fonts
badger.text("string", x, y, scale)
badger.line(x1, y1, x2, y2)
badger.rectangle(x, y, w, h)
badger.jpeg.open_file("path.jpg"); badger.jpeg.decode(x, y)
```

### Buttons
```python
badger.pressed(badger.BUTTON_A)  # A, B, C, UP, DOWN
badger.pressed_any()
badger.pressed_to_wake(button)   # Which button woke from sleep
```

### Power & Sleep
```python
badger.turn_off()                # Low-power halt; wake on button press
badger.sleep_for(minutes)        # RTC-triggered wake
badger.woken_by_button()
badger.woken_by_rtc()
badger.system_speed(speed)       # VERY_SLOW / SLOW / NORMAL / FAST / TURBO
badger.led(0-255)                # Indicator LED brightness
```

### Networking
```python
import network
import urequests               # HTTP GET/POST
import ntptime                 # NTP sync
import umqtt.simple            # MQTT
import mip                     # Package installer
```

### State Persistence
```python
import badger_os
badger_os.state_save("app_name", state_dict)
badger_os.state_load("app_name", state_dict)
```

---

## WiFi Configuration

Edit `secrets.py` on the device:
```python
WIFI_SSID = "your_network"
WIFI_PASSWORD = "your_password"
REGION = "eu"        # DST region for clock app
TIMEZONE = 0         # GMT offset in hours
```

---

## Adding a New App

1. Create `apps/yourapp/` directory
2. Add `apps/yourapp/__init__.py` with your logic
3. Add `apps/yourapp/icon.png` (the menu auto-discovers it)
4. The Menu app will list it automatically on next boot

Minimal app skeleton:
```python
import badger2040 as badger

badger.system_speed(badger.SYSTEM_NORMAL)
display = badger.Badger2040()
display.set_update_speed(badger.UPDATE_NORMAL)

display.set_pen(15)
display.clear()
display.set_pen(0)
display.set_font("bitmap8")
display.text("Hello, world!", 10, 50, scale=2)
display.update()

while True:
    if display.pressed(display.BUTTON_B):
        break  # Return to menu

import machine
machine.reset()
```

---

## Capability Gap Analysis

| Capability | Pre-installed? | Notes |
|---|---|---|
| Name badge display | ✅ Yes | Badge app, fully featured |
| WiFi connectivity | ✅ Yes | All W-dependent apps use it |
| Time / NTP sync | ✅ Yes | Clock app |
| HTTP requests | ✅ Yes | `urequests` available |
| MQTT messaging | ✅ Yes | `umqtt.simple` available |
| QR code display | ❌ Not on 2350 | Was in 2040 OS; not present here |
| News/RSS reader | ❌ Not on 2350 | Was in 2040 OS; not present here |
| Weather display | ❌ Not on 2350 | Was in 2040 OS; not present here |
| Image viewer | ❌ Not on 2350 | Was in 2040 OS; not present here |
| E-book reader | ❌ Not on 2350 | Was in 2040 OS; not present here |
| Task/list app | ❌ Not on 2350 | Was in 2040 OS; not present here |
| Persistent state | ✅ Yes | `badger_os.state_save/load` |
| Low-power sleep | ✅ Yes | `turn_off()`, `sleep_for()` |
| 3D raycasting | ✅ Yes (!) | The Compendium |
| Custom apps | ✅ Yes | Drop into `apps/` directory |

---

## Bottom Line

The Badger 2350 pre-install is a **focused, polished set** — less breadth than the older 2040 but higher quality per app. The infrastructure (WiFi, RTC, persistent state, font library, mass storage mode) is all there. The main gaps versus the 2040 are QR codes, RSS/news, weather, and image viewing — those would need to be written or ported from the `pimoroni/badger2040` GitHub repo (they're available there and should be compatible with modest adaptation).

If your use case involves **any network-fetched data, scheduling, or custom display logic**, the platform fully supports it — you're building on top of a solid foundation.
