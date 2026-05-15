import sys
import os
import json
import qrcode
from badgeware import State

sys.path.insert(0, "/system/apps/card")
os.chdir("/system/apps/card")

screen.antialias = screen.X2

_config = {}
for _path in ("card.local.json", "card.json"):
    try:
        with open(_path) as _f:
            _config = json.load(_f)
        break
    except OSError:
        pass

NAME = _config.get("name", "Your Name")
ROLE = _config.get("role", "Your Role")
COMPANY = _config.get("company", "Your Company")
EMAIL = _config.get("email", "you@example.com")
LINKEDIN = _config.get("linkedin", "yourhandle")
GITHUB = _config.get("github", "yourhandle")
CONTACT_URL = _config.get("contact_url", "")

W = screen.width
H = screen.height
CX = W / 2

HEADER_H = 26
FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12
CONTENT_H = FOOTER_LINE_Y - HEADER_H

small = rom_font.smart
large = rom_font.ignore

state = {"view": 0}
State.load("card", state)

_qr = None
if CONTACT_URL:
    _qr = qrcode.QRCode()
    _qr.set_text(CONTACT_URL)


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


def draw_name_view():
    screen.pen = color.white
    screen.clear()
    _header(COMPANY)

    name_y = HEADER_H + int(CONTENT_H * 0.30)
    role_y = HEADER_H + int(CONTENT_H * 0.65)

    screen.font = large
    screen.pen = color.black
    nw, _ = screen.measure_text(NAME)
    screen.text(NAME, CX - nw / 2, name_y)

    screen.font = small
    screen.text(ROLE, 8, role_y)

    _footer("B: share QR", "HOME: menu")


def draw_contact_view():
    screen.pen = color.white
    screen.clear()
    _header("Contact")

    email_y = HEADER_H + int(CONTENT_H * 0.15)
    linkedin_y = HEADER_H + int(CONTENT_H * 0.45)
    github_y = HEADER_H + int(CONTENT_H * 0.70)

    screen.font = small
    screen.pen = color.black
    screen.text(EMAIL, 8, email_y)
    screen.text("linkedin.com/in/" + LINKEDIN, 8, linkedin_y)
    screen.text("github.com/" + GITHUB, 8, github_y)

    _footer("B: back", "HOME: menu")


def draw_qr_view():
    screen.pen = color.white
    screen.clear()
    _header("Scan to add contact")

    if _qr is None:
        screen.pen = color.black
        screen.font = small
        screen.text("Add contact_url to", 8, 50)
        screen.text("card.local.json", 8, 68)
    else:
        w, _ = _qr.get_size()
        cell_size = max(1, min(CONTENT_H, 120) // w)
        total = cell_size * w
        ox = (W - total) // 2
        oy = HEADER_H + (CONTENT_H - total) // 2
        screen.pen = color.white
        screen.shape(shape.rectangle(ox, oy, total, total))
        screen.pen = color.black
        for x in range(w):
            for y in range(w):
                if _qr.get_module(x, y):
                    screen.shape(shape.rectangle(
                        ox + x * cell_size, oy + y * cell_size,
                        cell_size, cell_size))

    _footer("B: back", "HOME: menu")


_views = [draw_name_view, draw_contact_view, draw_qr_view]

_needs_redraw = True


def update():
    global _needs_redraw

    badge.default_clear = None

    if badge.pressed(BUTTON_B):
        state["view"] = 0 if state["view"] == 2 else 2
        State.modify("card", state)
        _needs_redraw = True
    elif state["view"] != 2:
        if badge.pressed(BUTTON_UP):
            state["view"] = (state["view"] - 1) % 2
            State.modify("card", state)
            _needs_redraw = True
        elif badge.pressed(BUTTON_DOWN):
            state["view"] = (state["view"] + 1) % 2
            State.modify("card", state)
            _needs_redraw = True

    if _needs_redraw:
        _needs_redraw = False
        _views[state["view"]]()
        badge.update()

    wait_for_button_or_alarm()


def on_exit():
    if state["view"] == 2:
        state["view"] = 0
        State.modify("card", state)


run(update)
