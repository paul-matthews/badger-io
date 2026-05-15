import sys
import os
import gc
import json
import bluetooth
import qrcode
from badgeware import State

sys.path.insert(0, "/system/apps/url_share")
os.chdir("/system/apps/url_share")

COMPANION_URL = "https://paul-matthews.github.io/badger-io/"

# /system/ is read-only at runtime; /state/ is the writable mount that all
# apps can read. Config the web app sends is persisted here; the card and
# topics apps read these same paths first. Distinct cfg_ names avoid
# colliding with the State API's own /state/<appname>.json files.
URLS_PATH   = "/state/cfg_urls.json"
CARD_PATH   = "/state/cfg_card.json"
TOPICS_PATH = "/state/cfg_topics.json"

try:
    os.mkdir("/state")
except OSError:
    pass

small = rom_font.smart
W = screen.width
H = screen.height
HEADER_H = 26
FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12

state = {"idx": 0}
State.load("url_share", state)


# ── Config files ──────────────────────────────────────────────────────────────

def _read_text(*paths):
    for p in paths:
        try:
            with open(p) as f:
                return f.read()
        except OSError:
            pass
    return ""


def _load_urls():
    for p in (URLS_PATH, "urls.json"):
        try:
            with open(p) as f:
                return json.load(f).get("urls", [])
        except (OSError, ValueError):
            pass
    return []


def _save_item(path, key, raw):
    """Merge a single {"i","l","u"} item into the {key:[...]} file at path."""
    try:
        item = json.loads(raw)
    except ValueError:
        return
    i = item.get("i", -1)
    if not isinstance(i, int) or i < 0 or i > 7:
        return
    data = {key: []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    lst = data.get(key, [])
    while len(lst) <= i:
        lst.append({"l": "", "u": ""})
    lst[i] = {"l": item.get("l", ""), "u": item.get("u", "")}
    while lst and not lst[-1].get("u"):
        lst.pop()
    data[key] = lst
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError as e:
        print("url_share: save failed", path, e)


def _save_raw(path, raw):
    """Validate raw is JSON and write it verbatim to path."""
    try:
        json.loads(raw)
    except ValueError:
        return
    try:
        with open(path, "w") as f:
            f.write(raw)
    except OSError as e:
        print("url_share: save failed", path, e)


urls = _load_urls()

# ── BLE ───────────────────────────────────────────────────────────────────────

_SVC_UUID    = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000001")
_URL_UUID    = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000002")
_CARD_UUID   = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000003")
_TOPICS_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000004")

_FLAG_READ  = 0x0002
_FLAG_WRITE = 0x0008

_ble = bluetooth.BLE()
_ble.active(True)

_url_handle    = None
_card_handle   = None
_topics_handle = None

# IRQ runs while the app sleeps; the web app sends up to 8 sequential per-item
# writes, so queue them (a single var would coalesce to the last write only).
_pending_url_items   = []
_pending_card        = None
_pending_topic_items = []


def _ble_irq(event, data):
    global _pending_card
    if event == 3:  # IRQ_GATTS_WRITE
        _, attr_handle = data
        if attr_handle == _url_handle:
            _pending_url_items.append(
                _ble.gatts_read(_url_handle).decode("utf-8").rstrip("\x00").strip())
        elif attr_handle == _card_handle:
            _pending_card = _ble.gatts_read(_card_handle).decode("utf-8").rstrip("\x00").strip()
        elif attr_handle == _topics_handle:
            _pending_topic_items.append(
                _ble.gatts_read(_topics_handle).decode("utf-8").rstrip("\x00").strip())


_ble.irq(_ble_irq)
((_url_handle, _card_handle, _topics_handle),) = _ble.gatts_register_services((
    (_SVC_UUID, (
        (_URL_UUID,    _FLAG_READ | _FLAG_WRITE),
        (_CARD_UUID,   _FLAG_READ | _FLAG_WRITE),
        (_TOPICS_UUID, _FLAG_READ | _FLAG_WRITE),
    )),
))
# Pre-allocate GATT buffers (default is tiny). URLs/topics hold the whole
# list for read-back/restore, so they need more room than card.
_BUFS = {_url_handle: 1024, _card_handle: 512, _topics_handle: 1024}
for _h, _sz in _BUFS.items():
    _ble.gatts_write(_h, b'\x00' * _sz)


def _expose(handle, *paths):
    """Publish the current config JSON as the characteristic's readable
    value so the web app can restore state on connect. Padded to the full
    buffer so write capacity is preserved."""
    txt = _read_text(*paths)
    sz = _BUFS[handle]
    b = txt.encode("utf-8")[:sz] if txt else b''
    _ble.gatts_write(handle, b + b'\x00' * (sz - len(b)))


_CARD_READ_PATHS = (CARD_PATH,
                    "/system/apps/card/card.local.json",
                    "/system/apps/card/card.json")

_expose(_url_handle, URLS_PATH, "urls.json")
_expose(_card_handle, *_CARD_READ_PATHS)
_expose(_topics_handle, TOPICS_PATH)

_adv_data  = b'\x02\x01\x06' + bytes([0x11, 0x07]) + bytes(_SVC_UUID)
_resp_data = bytes([0x0a, 0x09]) + b'Badger-IO'


def _start_advertising():
    _ble.gap_advertise(100_000, adv_data=_adv_data, resp_data=_resp_data)


def _stop_advertising():
    _ble.gap_advertise(None)


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
    screen.text("Press B, then open the", 8, 72)
    screen.text("web app in Chrome.", 8, 88)
    _footer("B: share")


def draw_advertising():
    screen.pen = color.white
    screen.clear()
    _header("Configure from a browser")

    gc.collect()
    companion_code = qrcode.QRCode()
    companion_code.set_text(COMPANION_URL)
    qr_total = _draw_qr(4, 30, companion_code)

    tx = qr_total + 12
    screen.pen = color.black
    screen.font = small
    screen.text("In Chrome/Edge:", tx, 36)
    screen.text("open the URL below,", tx, 52)
    screen.text("Connect, edit, Save,", tx, 68)
    screen.text("then press B.", tx, 84)

    # URL as readable text (a laptop can't scan the QR; phone users can)
    short = COMPANION_URL.replace("https://", "").replace("http://", "")
    if short.endswith("/"):
        short = short[:-1]
    screen.pen = color.black
    screen.font = small
    uw, _ = screen.measure_text(short)
    screen.text(short, (W - uw) // 2, H - 36)

    _footer("B: done")


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

_ble_active   = False
_needs_redraw = True


def update():
    global _ble_active, _needs_redraw, _pending_card, urls

    badge.default_clear = None

    # Drain queued BLE config writes (web app sends these while we sleep;
    # they are applied when the user presses a button — e.g. B to finish).
    if _pending_url_items:
        while _pending_url_items:
            _save_item(URLS_PATH, "urls", _pending_url_items.pop(0))
        urls = _load_urls()
        if state["idx"] >= len(urls):
            state["idx"] = 0
        _expose(_url_handle, URLS_PATH, "urls.json")
        _needs_redraw = True

    if _pending_card is not None:
        raw, _pending_card = _pending_card, None
        _save_raw(CARD_PATH, raw)
        _expose(_card_handle, *_CARD_READ_PATHS)

    if _pending_topic_items:
        while _pending_topic_items:
            _save_item(TOPICS_PATH, "topics", _pending_topic_items.pop(0))
        _expose(_topics_handle, TOPICS_PATH)

    if badge.pressed(BUTTON_B):
        if _ble_active:
            _stop_advertising()
            _ble_active = False
        else:
            try:
                _start_advertising()
                _ble_active = True
            except Exception as e:
                print("url_share: gap_advertise failed:", e)
        _needs_redraw = True
    elif not _ble_active and urls:
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
        if _ble_active:
            draw_advertising()
        elif urls:
            draw_url_list(state["idx"] % len(urls))
        else:
            draw_no_urls()
        badge.update()

    wait_for_button_or_alarm()


def on_exit():
    if _ble_active:
        _stop_advertising()


run(update)
