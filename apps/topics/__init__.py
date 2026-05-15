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
large = rom_font.ignore
W = screen.width
H = screen.height

FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12

state = {"idx": 0}
State.load("topics", state)

_needs_redraw = True


def _footer(left, right="HOME: menu"):
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.font = small
    screen.pen = color.black
    screen.text(left, 8, FOOTER_TEXT_Y)
    if right:
        rw, _ = screen.measure_text(right)
        screen.text(right, W - rw - 8, FOOTER_TEXT_Y)


def _wrap(s, max_w):
    """Greedy word wrap at the current font; falls back to char split."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        tw, _ = screen.measure_text(trial)
        if tw <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _line_h():
    _, h = screen.measure_text("Ag")
    return h + 4


def draw_topic(idx):
    topic = topics[idx]
    label = topic.get("l", "")
    url = topic.get("u", "")

    screen.pen = color.white
    screen.clear()

    # ── Big QR on the right ──────────────────────────────────────────────
    qr_x = W
    if url:
        gc.collect()
        code = qrcode.QRCode()
        code.set_text(url)
        qw, _ = code.get_size()
        cell = max(1, min(FOOTER_LINE_Y - 8, 152) // qw)
        total = cell * qw
        qr_x = W - 6 - total
        qr_y = (FOOTER_LINE_Y - total) // 2
        screen.pen = color.white
        screen.shape(shape.rectangle(qr_x, qr_y, total, total))
        screen.pen = color.black
        for x in range(qw):
            for y in range(qw):
                if code.get_module(x, y):
                    screen.shape(shape.rectangle(
                        qr_x + x * cell, qr_y + y * cell, cell, cell))
    else:
        qr_x = W - 6

    # ── "Ask me about" / <topic> on the left, large font ────────────────
    lx = 8
    lw = qr_x - lx - 10
    screen.font = large
    head = _wrap("Ask me about", lw)
    body = _wrap(label, lw) if label else []
    lh = _line_h()
    block_h = (len(head) + len(body)) * lh + (8 if body else 0)
    y = max(4, (FOOTER_LINE_Y - block_h) // 2)

    screen.pen = color.black
    for ln in head:
        screen.text(ln, lx, y)
        y += lh
    y += 8
    for ln in body:
        screen.text(ln, lx, y)
        y += lh

    counter = "{}/{}".format(idx + 1, len(topics))
    _footer(counter + "   UP/DN: page")


def draw_empty():
    screen.pen = color.white
    screen.clear()
    screen.font = large
    screen.pen = color.black
    lh = _line_h()
    screen.text("Ask me about", 8, 28)
    screen.font = small
    screen.text("No topics yet.", 8, 28 + lh + 12)
    screen.text("Configure via the URL Share app.", 8, 28 + lh + 32)
    _footer("")


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
