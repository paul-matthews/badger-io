"""Conference schedule — loads from /data/schedule.local.json or /data/schedule.json.

Shows currently highlighted sessions that are happening now or coming up.
Time is read from the device RTC (synced by the Clock app via NTP).

Navigation:
  UP/DOWN    — scroll through highlighted sessions
  A          — force NTP time sync (requires WiFi)
  B          — return to launcher
  A+C        — return to launcher (standard BadgeOS exit)
"""
import badger2040
import badger_os
import json
import machine
import network
import ntptime
import time

WIDTH = badger2040.WIDTH   # 296
HEIGHT = badger2040.HEIGHT  # 128

SCHED_PATH = "/data/schedule.json"
SCHED_LOCAL_PATH = "/data/schedule.local.json"

WIFI_CONFIG_PATH = "/WIFI_CONFIG.py"


def load_schedule():
    for path in (SCHED_LOCAL_PATH, SCHED_PATH):
        try:
            with open(path) as f:
                return json.load(f)
        except OSError:
            pass
    return {"sessions": []}


def now_hhmm():
    """Return current RTC time as (date_str YYYY-MM-DD, hhmm int)."""
    dt = machine.RTC().datetime()
    # dt: (year, month, day, weekday, hour, minute, second, subsecond)
    date_str = "{:04d}-{:02d}-{:02d}".format(dt[0], dt[1], dt[2])
    hhmm = dt[4] * 60 + dt[5]
    return date_str, hhmm


def parse_hhmm(t):
    """'14:30' → 870 (minutes since midnight)."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def session_status(session, date_str, now):
    """Returns 'now', 'soon' (≤60 min away), or None."""
    if session.get("date") != date_str:
        return None
    start = parse_hhmm(session["start"])
    end = parse_hhmm(session["end"])
    if start <= now < end:
        return "now"
    if 0 < start - now <= 60:
        return "soon"
    return None


def ntp_sync():
    try:
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            return False
        ntptime.settime()
        return True
    except Exception:
        return False


display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)
display.set_thickness(2)

schedule = load_schedule()
all_sessions = schedule.get("sessions", [])

state = {"offset": 0}
badger_os.state_load("schedule", state)

_status_msg = ""


def get_relevant(date_str, now):
    """Return highlighted sessions that are NOW or SOON, sorted by start time."""
    result = []
    for s in all_sessions:
        if not s.get("highlighted"):
            continue
        st = session_status(s, date_str, now)
        if st:
            result.append((st, s))
    result.sort(key=lambda x: parse_hhmm(x[1]["start"]))
    return result


def draw_header(date_str, hhmm):
    """Black header bar with conference name and current time."""
    display.set_pen(0)
    display.rectangle(0, 0, WIDTH, 22)
    display.set_pen(15)
    display.set_font("bitmap8")
    conf = schedule.get("conference", "Schedule")
    display.text(conf, 6, 7, 200, 1)
    time_str = "{:02d}:{:02d}".format(hhmm // 60, hhmm % 60)
    time_w = display.measure_text(time_str, 1)
    display.text(time_str, WIDTH - time_w - 6, 7, 80, 1)


def draw_session(y, status, session, highlight_now):
    """Draw a single session row."""
    row_h = 38
    if highlight_now and status == "now":
        display.set_pen(0)
        display.rectangle(0, y, WIDTH, row_h)
        fg = 15
    else:
        display.set_pen(15)
        display.rectangle(0, y, WIDTH, row_h)
        fg = 0

    display.set_pen(fg)

    # Status badge
    badge = " NOW " if status == "now" else "SOON"
    display.set_font("bitmap8")
    display.text(badge, 4, y + 4, 36, 1)

    # Time
    time_str = session["start"] + "-" + session["end"]
    display.text(time_str, 4, y + 18, 80, 1)

    # Title
    display.set_font("sans")
    title = session.get("title", "")
    display.text(title, 52, y + 6, WIDTH - 100, 0.5)

    # Location
    display.set_font("bitmap8")
    loc = session.get("location", "")
    display.text(loc, 52, y + 22, WIDTH - 60, 1)

    # Track tag right-aligned
    track = session.get("track", "")
    if track:
        tw = display.measure_text(track, 1)
        display.text(track, WIDTH - tw - 4, y + 4, 80, 1)


def draw_schedule():
    global state
    date_str, hhmm = now_hhmm()
    relevant = get_relevant(date_str, hhmm)

    display.set_pen(15)
    display.clear()
    draw_header(date_str, hhmm)

    if not relevant:
        display.set_pen(0)
        display.set_font("sans")
        display.text("No highlighted sessions right now.", 8, 60, WIDTH - 16, 0.55)
        display.set_font("bitmap8")
        display.text("Sessions shown within 60 min of start.", 8, 88, WIDTH - 16, 1)
    else:
        offset = state["offset"] % len(relevant)
        visible = relevant[offset:offset + 2]
        y = 24
        for i, (st, sess) in enumerate(visible):
            draw_session(y, st, sess, i == 0)
            y += 40
            if y + 38 > HEIGHT - 16:
                break

        # Scroll indicator
        if len(relevant) > 1:
            display.set_pen(0)
            for i in range(len(relevant)):
                dot_y = HEIGHT - 12 + (i * 6 - len(relevant) * 3)
                if i == offset:
                    display.rectangle(WIDTH - 8, dot_y, 5, 5)
                else:
                    display.rectangle(WIDTH - 7, dot_y + 1, 3, 3)

    # Status message (e.g. "NTP synced")
    if _status_msg:
        display.set_pen(15)
        display.rectangle(0, HEIGHT - 14, WIDTH - 12, 14)
        display.set_pen(0)
        display.set_font("bitmap8")
        display.text(_status_msg, 4, HEIGHT - 11, WIDTH - 16, 1)

    display.line(0, HEIGHT - 16, WIDTH - 12, HEIGHT - 16)
    display.set_font("bitmap8")
    display.set_pen(0)
    display.text("UP/DN: scroll  A: sync  B: menu", 4, HEIGHT - 11, WIDTH - 14, 1)

    display.update()


draw_schedule()

while True:
    display.keepalive()
    changed = False

    date_str, hhmm = now_hhmm()
    relevant = get_relevant(date_str, hhmm)

    if display.pressed(badger2040.BUTTON_UP):
        if relevant:
            state["offset"] = (state["offset"] - 1) % max(len(relevant), 1)
        changed = True

    if display.pressed(badger2040.BUTTON_DOWN):
        if relevant:
            state["offset"] = (state["offset"] + 1) % max(len(relevant), 1)
        changed = True

    if display.pressed(badger2040.BUTTON_A):
        _status_msg = "Syncing..."
        draw_schedule()
        if ntp_sync():
            _status_msg = "NTP synced"
        else:
            _status_msg = "Sync failed (no WiFi?)"
        changed = True

    if display.pressed(badger2040.BUTTON_B):
        break

    if changed:
        badger_os.state_save("schedule", state)
        draw_schedule()

    display.halt()

import machine
machine.reset()
