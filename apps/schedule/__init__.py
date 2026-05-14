import sys
import os
import json
import machine
from badgeware import run, State

sys.path.insert(0, "/system/apps/schedule")
os.chdir("/system/apps/schedule")

_config = {}
for _path in ("schedule.local.json", "schedule.json"):
    try:
        with open(_path) as _f:
            _config = json.load(_f)
        break
    except OSError:
        pass

CONFERENCE = _config.get("conference", "Schedule")
ALL_SESSIONS = _config.get("sessions", [])

small = rom_font.smart
W = screen.width
H = screen.height

state = {"offset": 0}
State.load("schedule", state)

_last_up = False
_last_dn = False


def _now_hhmm():
    dt = machine.RTC().datetime()
    # (year, month, day, weekday, hour, minute, second, subsecond)
    date_str = "{:04d}-{:02d}-{:02d}".format(dt[0], dt[1], dt[2])
    return date_str, dt[4] * 60 + dt[5]


def _parse_hhmm(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _status(session, date_str, now):
    if session.get("date") != date_str:
        return None
    start = _parse_hhmm(session["start"])
    end = _parse_hhmm(session["end"])
    if start <= now < end:
        return "NOW"
    if 0 < start - now <= 60:
        return "SOON"
    return None


def _relevant(date_str, now):
    result = []
    for s in ALL_SESSIONS:
        if not s.get("highlighted"):
            continue
        st = _status(s, date_str, now)
        if st:
            result.append((st, s))
    result.sort(key=lambda x: _parse_hhmm(x[1]["start"]))
    return result


def _draw_session(y, label, session):
    row_h = 40
    is_now = label == "NOW"

    if is_now:
        screen.pen = color.black
        screen.shape(shape.rectangle(0, y, W, row_h))
        screen.pen = color.white
    else:
        screen.pen = color.light_grey
        screen.shape(shape.rectangle(0, y, W, row_h))
        screen.pen = color.black

    screen.font = small
    screen.text(label, 4, y + 4)
    screen.text("{}-{}".format(session["start"], session["end"]), 4, y + 20)

    title = session.get("title", "")
    screen.text(title, 52, y + 4)

    loc = session.get("location", "")
    screen.text(loc, 52, y + 20)

    track = session.get("track", "")
    if track:
        tw, _ = screen.measure_text(track)
        screen.text(track, W - tw - 4, y + 4)


def update():
    global _last_up, _last_dn

    up_now = io.BUTTON_UP in io.pressed
    dn_now = io.BUTTON_DOWN in io.pressed

    date_str, hhmm = _now_hhmm()
    relevant = _relevant(date_str, hhmm)

    if up_now and not _last_up and relevant:
        state["offset"] = (state["offset"] - 1) % len(relevant)
        State.modify("schedule", state)
    if dn_now and not _last_dn and relevant:
        state["offset"] = (state["offset"] + 1) % len(relevant)
        State.modify("schedule", state)

    _last_up = up_now
    _last_dn = dn_now

    screen.pen = color.white
    screen.clear()

    # Header
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, 26))
    screen.pen = color.white
    screen.font = small
    screen.text(CONFERENCE, 8, 8)
    time_str = "{:02d}:{:02d}".format(hhmm // 60, hhmm % 60)
    tw, _ = screen.measure_text(time_str)
    screen.text(time_str, W - tw - 8, 8)

    if not relevant:
        screen.pen = color.black
        screen.font = small
        screen.text("No highlighted sessions right now.", 8, 50)
        screen.text("Sessions shown within 60 min", 8, 68)
        screen.text("of their start time.", 8, 84)
    else:
        offset = state["offset"] % len(relevant)
        visible = relevant[offset:offset + 2]
        y = 28
        for label, sess in visible:
            _draw_session(y, label, sess)
            y += 42

        if len(relevant) > 1:
            screen.pen = color.dark_grey
            screen.font = small
            screen.text("{}/{}".format(offset + 1, len(relevant)), W - 28, H - 12)

    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, 110, W, 1))
    screen.font = small
    screen.pen = color.black
    screen.text("UP/DN: scroll", 8, 116)
    screen.text("A+C: menu", 200, 116)


def init():
    pass


def on_exit():
    pass


if __name__ == "__main__":
    run(update)
