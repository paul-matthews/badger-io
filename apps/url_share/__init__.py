import sys
import os
import gc
import json
import qrcode
from badgeware import State

sys.path.insert(0, "/system/apps/url_share")
os.chdir("/system/apps/url_share")

# Read-only viewer. Configuration (the urls list) is received over Bluetooth
# by the separate Settings app, which writes /state/cfg_urls.json. This app
# only displays it. urls.json (shipped beside this app) is the seed fallback.
URLS_PATH = "/state/cfg_urls.json"

small = rom_font.smart
W = screen.width
H = screen.height
HEADER_H = 26
FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12

state = {"idx": 0}
State.load("url_share", state)


def _load_urls():
    for p in (URLS_PATH, "urls.json"):
        try:
            with open(p) as f:
                return json.load(f).get("urls", [])
        except (OSError, ValueError):
            pass
    return []


urls = _load_urls()


# ── Drawing ───────────────────────────────────────────────────────────────────

def _header(label, right=None):
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, HEADER_H))
    screen.pen = color.white
    screen.font = small
    screen.text(label, 8, 8)
    if right:
        rw, _ = screen.measure_text(right)
        screen.text(right, W - rw - 8, 8)


def _footer(left, right="HOME: menu"):
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.font = small
    screen.pen = color.black
    screen.text(left, 8, FOOTER_TEXT_Y)
    if right:
        rw, _ = screen.measure_text(right)
        screen.text(right, W - rw - 8, FOOTER_TEXT_Y)


def _draw_qr(ox, oy, code):
    w, _ = code.get_size()
    cell_size = max(1, min(H - 36, 84) // w)
    total = cell_size * w
    screen.pen = color.white
    screen.shape(shape.rectangle(ox, oy, total, total))
    screen.pen = color.black
    for x in range(w):
        for y in range(w):
            if code.get_module(x, y):
                screen.shape(shape.rectangle(ox + x * cell_size, oy + y * cell_size, cell_size, cell_size))
    return total


def _wrap(s, max_w, max_lines):
    screen.font = small
    lines = []
    cur = ""
    for ch in s:
        t = cur + ch
        tw, _ = screen.measure_text(t)
        if tw > max_w:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                return lines
        else:
            cur = t
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def draw_no_urls():
    screen.pen = color.white
    screen.clear()
    _header("URL Share")
    screen.pen = color.black
    screen.font = small
    screen.text("No URLs yet.", 8, 52)
    screen.text("Configure via the", 8, 72)
    screen.text("Settings app.", 8, 88)
    _footer("")


def draw_url_list(idx):
    entry = urls[idx]
    label = entry.get("l", "")
    url = entry.get("u", "")

    screen.pen = color.white
    screen.clear()
    _header(label or "URL Share", "{}/{}".format(idx + 1, len(urls)))

    if url:
        gc.collect()
        code = qrcode.QRCode()
        code.set_text(url)
        qr_total = _draw_qr(4, 34, code)
        tx = qr_total + 12
        screen.pen = color.black
        screen.font = small
        short = url.replace("https://", "").replace("http://", "")
        y = 44
        for line in _wrap(short, W - tx - 8, 5):
            screen.text(line, tx, y)
            y += 16
    else:
        screen.pen = color.black
        screen.font = small
        screen.text("(no URL set)", 8, HEADER_H + 30)

    _footer("UP/DN: page")


# ── App loop ──────────────────────────────────────────────────────────────────

_needs_redraw = True


def update():
    global _needs_redraw

    badge.default_clear = None

    if urls:
        if badge.pressed(BUTTON_UP):
            state["idx"] = (state["idx"] - 1) % len(urls)
            State.modify("url_share", state)
            _needs_redraw = True
        elif badge.pressed(BUTTON_DOWN):
            state["idx"] = (state["idx"] + 1) % len(urls)
            State.modify("url_share", state)
            _needs_redraw = True

    if _needs_redraw:
        _needs_redraw = False
        if urls:
            draw_url_list(state["idx"] % len(urls))
        else:
            draw_no_urls()
        badge.update()

    wait_for_button_or_alarm()


def on_exit():
    pass


run(update)
