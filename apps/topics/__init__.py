import sys
import os
import gc
import json
import qrcode
from badgeware import State

sys.path.insert(0, "/system/apps/topics")
os.chdir("/system/apps/topics")

_config = {}
for _path in ("/state/cfg_topics.json", "topics.json"):
    try:
        with open(_path) as _f:
            _config = json.load(_f)
        break
    except (OSError, ValueError):
        pass

topics = _config.get("topics", [])

small = rom_font.smart
W = screen.width
H = screen.height

HEADER_H = 26
FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12
CONTENT_H = FOOTER_LINE_Y - HEADER_H

state = {"idx": 0}
State.load("topics", state)

_needs_redraw = True


def _header(label):
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, HEADER_H))
    screen.pen = color.white
    screen.font = small
    screen.text(label, 8, 8)


def _footer(left, right=None):
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.font = small
    screen.pen = color.black
    screen.text(left, 8, FOOTER_TEXT_Y)
    if right:
        rw, _ = screen.measure_text(right)
        screen.text(right, W - rw - 8, FOOTER_TEXT_Y)


def draw_empty():
    screen.pen = color.white
    screen.clear()
    _header("Ask Me About")
    screen.pen = color.black
    screen.font = small
    screen.text("No topics yet.", 8, 56)
    screen.text("Configure via the", 8, 76)
    screen.text("URL Share app.", 8, 92)
    _footer("", "HOME: menu")


def draw_topic(idx):
    topic = topics[idx]
    label = topic.get("l", "")
    url = topic.get("u", "")

    screen.pen = color.white
    screen.clear()

    counter = "{}/{}".format(idx + 1, len(topics))
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, HEADER_H))
    screen.pen = color.white
    screen.font = small
    cw, _ = screen.measure_text(counter)
    screen.text(label, 8, 8)
    screen.text(counter, W - cw - 8, 8)

    if url:
        gc.collect()
        code = qrcode.QRCode()
        code.set_text(url)
        w, _ = code.get_size()
        cell_size = max(1, min(CONTENT_H, 120) // w)
        total = cell_size * w
        ox = (W - total) // 2
        oy = HEADER_H + (CONTENT_H - total) // 2
        screen.pen = color.white
        screen.shape(shape.rectangle(ox, oy, total, total))
        screen.pen = color.black
        for x in range(w):
            for y in range(w):
                if code.get_module(x, y):
                    screen.shape(shape.rectangle(
                        ox + x * cell_size, oy + y * cell_size,
                        cell_size, cell_size))
    else:
        screen.pen = color.black
        screen.font = small
        screen.text("(no URL set)", 8, HEADER_H + 30)

    _footer("UP/DN: page", "HOME: menu")


def update():
    global _needs_redraw

    badge.default_clear = None

    n = len(topics)
    if n:
        if badge.pressed(BUTTON_UP):
            state["idx"] = (state["idx"] - 1) % n
            State.modify("topics", state)
            _needs_redraw = True
        elif badge.pressed(BUTTON_DOWN):
            state["idx"] = (state["idx"] + 1) % n
            State.modify("topics", state)
            _needs_redraw = True

    if _needs_redraw:
        _needs_redraw = False
        if n:
            draw_topic(state["idx"] % n)
        else:
            draw_empty()
        badge.update()

    wait_for_button_or_alarm()


def on_exit():
    pass


run(update)
