import sys
import os
from badgeware import State

sys.path.insert(0, "/system/apps/menu")
os.chdir("/system/apps/menu")

APPS_DIR = "/system/apps"
EXCLUDED = {"menu", "startup"}

W = screen.width
H = screen.height
small = rom_font.smart

_apps = []
for name in sorted(os.listdir(APPS_DIR)):
    if name not in EXCLUDED:
        try:
            os.stat(APPS_DIR + "/" + name + "/__init__.py")
            _apps.append(name)
        except OSError:
            pass

_selected = 0
_prev_selected = -1  # -1 forces full redraw on first render
_last_up = False
_last_dn = False
_last_b = False
_needs_redraw = True

state = {"selected": 0}
State.load("menu_cursor", state)
_selected = state.get("selected", 0) % max(1, len(_apps))

ROW_Y0 = 36
ROW_H  = 22
ROW_PAD = 4


def _label(name):
    label = name.replace("_", " ")
    return label[0].upper() + label[1:] if label else label


def _draw_row(i):
    y = ROW_Y0 + i * ROW_H
    if i == _selected:
        screen.pen = color.black
        screen.shape(shape.rectangle(0, y - ROW_PAD, W, ROW_H))
        screen.pen = color.white
    else:
        screen.pen = color.white
        screen.shape(shape.rectangle(0, y - ROW_PAD, W, ROW_H))
        screen.pen = color.black
    screen.font = small
    screen.text(_label(_apps[i]), 12, y)


def _draw_full():
    screen.pen = color.white
    screen.clear()
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, 26))
    screen.pen = color.white
    screen.font = small
    screen.text("Select App", 8, 8)

    for i in range(len(_apps)):
        _draw_row(i)

    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, H - 18, W, 1))
    screen.pen = color.black
    screen.font = small
    screen.text("UP/DN: nav  B: select", 8, H - 12)


def update():
    global _selected, _prev_selected, _last_up, _last_dn, _last_b, _needs_redraw

    up = io.BUTTON_UP in io.pressed
    dn = io.BUTTON_DOWN in io.pressed
    b = io.BUTTON_B in io.pressed

    if up and not _last_up:
        _selected = (_selected - 1) % len(_apps)
        _needs_redraw = True
    elif dn and not _last_dn:
        _selected = (_selected + 1) % len(_apps)
        _needs_redraw = True

    if b and not _last_b:
        state["selected"] = _selected
        State.modify("menu_cursor", state)
        return APPS_DIR + "/" + _apps[_selected]

    if _needs_redraw:
        if _prev_selected == -1:
            _draw_full()
        else:
            _draw_row(_prev_selected)
            _draw_row(_selected)
        _prev_selected = _selected
        _needs_redraw = False

    _last_up = up
    _last_dn = dn
    _last_b = b


run(update)
