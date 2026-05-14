import sys
import os
import json
from badgeware import run, State

sys.path.insert(0, "/system/apps/card")
os.chdir("/system/apps/card")

screen.antialias = image.X2

# Load card config — try card.local.json first, fall back to card.json
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

CX = screen.width / 2

small = rom_font.smart
large = rom_font.ignore

state = {"view": 0}
State.load("card", state)

_last_b = False


def _header(label):
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, screen.width, 26))
    screen.pen = color.white
    screen.font = small
    screen.text(label, 8, 8)


def draw_name_view():
    screen.pen = color.white
    screen.clear()

    _header(COMPANY)

    # Name — centred
    screen.font = large
    screen.pen = color.black
    nw, _ = screen.measure_text(NAME)
    screen.text(NAME, CX - nw / 2, 46)

    # Role
    screen.font = small
    screen.text(ROLE, 8, 92)

    # Divider + hint
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, 110, screen.width, 1))
    screen.text("B: contacts", 8, 116)
    screen.text("HOME: menu", 200, 116)


def draw_contact_view():
    screen.pen = color.white
    screen.clear()

    _header("Contact")

    screen.font = small
    screen.pen = color.black
    screen.text(EMAIL, 8, 38)
    screen.text("linkedin.com/in/" + LINKEDIN, 8, 62)
    screen.text("github.com/" + GITHUB, 8, 86)

    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, 110, screen.width, 1))
    screen.text("B: back", 8, 116)


_views = [draw_name_view, draw_contact_view]


def init():
    pass


def update():
    global _last_b
    b_now = io.BUTTON_B in io.pressed
    if b_now and not _last_b:
        state["view"] = 1 - state["view"]
        State.modify("card", state)
    _last_b = b_now

    _views[state["view"]]()


def on_exit():
    pass


if __name__ == "__main__":
    run(update)
