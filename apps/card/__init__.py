import sys
import os
import json
from badgeware import run, State

sys.path.insert(0, "/system/apps/card")
os.chdir("/system/apps/card")

screen.antialias = image.X2

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

_last_up = False
_last_dn = False


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

    _footer("UP/DN: contacts", "HOME: menu")


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

    _footer("UP/DN: back", "HOME: menu")


_views = [draw_name_view, draw_contact_view]


def init():
    print("card: init")


def update():
    global _last_up, _last_dn
    up_now = io.BUTTON_UP in io.pressed
    dn_now = io.BUTTON_DOWN in io.pressed
    n = len(_views)
    if up_now and not _last_up:
        state["view"] = (state["view"] - 1) % n
        State.modify("card", state)
    elif dn_now and not _last_dn:
        state["view"] = (state["view"] + 1) % n
        State.modify("card", state)
    _last_up = up_now
    _last_dn = dn_now

    _views[state["view"]]()


def on_exit():
    pass


run(update)
