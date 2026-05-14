"""Business card display — loads from /data/card.local.json or /data/card.json.

Navigation:
  B          — flip between name/role view and contact details view
  A + C      — return to launcher (standard BadgeOS exit)
"""
import badger2040
import badger_os
import json

WIDTH = badger2040.WIDTH   # 296
HEIGHT = badger2040.HEIGHT  # 128

CARD_PATH = "/data/card.json"
CARD_LOCAL_PATH = "/data/card.local.json"

DEFAULT_CARD = {
    "name": "Your Name",
    "company": "Your Company",
    "role": "Your Role",
    "email": "you@example.com",
    "linkedin": "yourhandle",
    "github": "yourhandle",
}


def load_card():
    for path in (CARD_LOCAL_PATH, CARD_PATH):
        try:
            with open(path) as f:
                return json.load(f)
        except OSError:
            pass
    return DEFAULT_CARD


display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)
display.set_thickness(2)

card = load_card()

state = {"view": 0}
badger_os.state_load("card", state)


def _fit_text(text, max_width, start_scale):
    """Scale text down until it fits within max_width."""
    scale = start_scale
    while scale > 0.4:
        if display.measure_text(text, scale) <= max_width:
            return scale
        scale -= 0.05
    return scale


def draw_name_view():
    """Primary view: name large, role and company below."""
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    # Company — top bar
    display.set_pen(0)
    display.rectangle(0, 0, WIDTH, 24)
    display.set_pen(15)
    display.set_font("sans")
    display.text(card.get("company", ""), 8, 12, WIDTH - 10, 0.5)

    # Name — centred, scaled to fit
    display.set_pen(0)
    display.set_font("sans")
    name = card.get("name", "")
    name_scale = _fit_text(name, WIDTH - 20, 1.8)
    name_w = display.measure_text(name, name_scale)
    display.text(name, (WIDTH - name_w) // 2, 44, WIDTH, name_scale)

    # Role
    display.set_font("sans")
    role = card.get("role", "")
    display.text(role, 8, 86, WIDTH - 10, 0.6)

    # Divider
    display.line(0, 108, WIDTH, 108)

    # Button hint
    display.set_font("bitmap8")
    display.text("B: contacts", 8, 116, 150, 1)
    display.text("A+C: menu", 210, 116, 90, 1)

    display.update()


def draw_contact_view():
    """Secondary view: email, LinkedIn, GitHub."""
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    # Header bar
    display.rectangle(0, 0, WIDTH, 24)
    display.set_pen(15)
    display.set_font("sans")
    display.text("Contact", 8, 12, 200, 0.55)

    display.set_pen(0)
    display.set_font("sans")

    y = 34
    pairs = [
        ("email",    card.get("email", "")),
        ("linkedin", "in/" + card.get("linkedin", "")),
        ("github",   "gh/" + card.get("github", "")),
    ]
    for label, value in pairs:
        display.set_font("bitmap8")
        display.text(label, 8, y, 70, 1)
        display.set_font("sans")
        display.text(value, 72, y + 2, WIDTH - 80, 0.55)
        y += 26

    display.line(0, 108, WIDTH, 108)
    display.set_font("bitmap8")
    display.text("B: back", 8, 116, 150, 1)

    display.update()


VIEWS = [draw_name_view, draw_contact_view]
VIEWS[state["view"]]()

while True:
    display.keepalive()

    if display.pressed(badger2040.BUTTON_B):
        state["view"] = 1 - state["view"]
        badger_os.state_save("card", state)
        VIEWS[state["view"]]()

    display.halt()
