import sys
import os
import gc
import json
import bluetooth
import qrcode

sys.path.insert(0, "/system/apps/settings")
os.chdir("/system/apps/settings")

COMPANION_URL = "https://paul-matthews.github.io/badger-io/"

# /system/ is read-only at runtime; /state/ is the writable mount that all
# apps can read. Config the web app sends is persisted here; the card, topics
# and url_share apps read these same paths first. Distinct cfg_ names avoid
# colliding with the State API's own /state/<appname>.json files.
URLS_PATH   = "/state/cfg_urls.json"
CARD_PATH   = "/state/cfg_card.json"
TOPICS_PATH = "/state/cfg_topics.json"

# os.chdir() above is /system/apps/settings, so the url_share seed file must
# be referenced absolutely (a bare "urls.json" would resolve here, wrongly).
URLS_SEED = "/system/apps/url_share/urls.json"

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

VIEW_DEFAULT = 0
VIEW_COMMITTED = 1


# ── Config files ──────────────────────────────────────────────────────────────

def _read_text(*paths):
    for p in paths:
        try:
            with open(p) as f:
                return f.read()
        except OSError:
            pass
    return ""


def _load_list(path, key):
    """Load a {key:[{l,u}...]} file and normalise to exactly 8 (l,u) tuples.
    Padding to a fixed length keeps slot indexes aligned for change-counting
    even though _save_item trims trailing empty slots."""
    try:
        with open(path) as f:
            lst = json.load(f).get(key, [])
    except (OSError, ValueError):
        lst = []
    out = []
    for i in range(8):
        e = lst[i] if i < len(lst) and isinstance(lst[i], dict) else {}
        out.append((e.get("l", ""), e.get("u", "")))
    return out


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
        print("settings: save failed", path, e)


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
        print("settings: save failed", path, e)


def _card_changed(old_txt, new_txt):
    if old_txt == new_txt:
        return False
    try:
        return json.loads(old_txt or "{}") != json.loads(new_txt or "{}")
    except ValueError:
        return (old_txt or "") != (new_txt or "")


# ── BLE ───────────────────────────────────────────────────────────────────────

_SVC_UUID    = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000001")
_URL_UUID    = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000002")
_CARD_UUID   = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000003")
_TOPICS_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000004")

_FLAG_READ  = 0x0002
_FLAG_WRITE = 0x0008

_url_handle    = None
_card_handle   = None
_topics_handle = None

# IRQ runs while the app sleeps; the web app sends up to 8 sequential per-item
# writes, so queue them (a single var would coalesce to the last write only).
# These persist across wait_for_button_or_alarm() wakes and are only drained
# when the user presses B.
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


_BUFS = {}
_CARD_READ_PATHS = (CARD_PATH,
                    "/system/apps/card/card.local.json",
                    "/system/apps/card/card.json")

_adv_data  = b'\x02\x01\x06' + bytes([0x11, 0x07]) + bytes(_SVC_UUID)
_resp_data = bytes([0x0a, 0x09]) + b'Badger-IO'


def _expose(handle, *paths):
    """Publish the current config JSON as the characteristic's readable
    value so the web app can restore state on connect. Padded to the full
    buffer so write capacity is preserved."""
    txt = _read_text(*paths)
    sz = _BUFS[handle]
    b = txt.encode("utf-8")[:sz] if txt else b''
    _ble.gatts_write(handle, b + b'\x00' * (sz - len(b)))


def _start_advertising():
    _ble.gap_advertise(100_000, adv_data=_adv_data, resp_data=_resp_data)


def _stop_advertising():
    _ble.gap_advertise(None)


# BLE up the moment the app opens; advertising starts immediately so the web
# app can connect without any button press. Mirrors url_share's proven setup.
_ble = None
try:
    _ble = bluetooth.BLE()
    _ble.active(True)
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
    _expose(_url_handle, URLS_PATH, URLS_SEED)
    _expose(_card_handle, *_CARD_READ_PATHS)
    _expose(_topics_handle, TOPICS_PATH)
    _start_advertising()
except Exception as e:
    print("settings: BLE init failed:", e)

gc.collect()


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


def draw_default():
    screen.pen = color.white
    screen.clear()
    _header("Settings")

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
    screen.text("then press B to apply.", tx, 84)

    short = COMPANION_URL.replace("https://", "").replace("http://", "")
    if short.endswith("/"):
        short = short[:-1]
    uw, _ = screen.measure_text(short)
    screen.text(short, (W - uw) // 2, H - 36)

    _footer("B: apply (do this before HOME)")


def draw_committed(n):
    screen.pen = color.white
    screen.clear()
    _header("Settings")

    if n <= 0:
        msg = "No changes to apply."
    elif n == 1:
        msg = "Applied 1 change."
    else:
        msg = "Applied {} changes.".format(n)

    screen.pen = color.black
    screen.font = small
    mw, _ = screen.measure_text(msg)
    screen.text(msg, (W - mw) // 2, 64)

    sub = "Send more from the web app,"
    sub2 = "then press B again."
    sw, _ = screen.measure_text(sub)
    sw2, _ = screen.measure_text(sub2)
    screen.text(sub, (W - sw) // 2, 92)
    screen.text(sub2, (W - sw2) // 2, 108)

    _footer("B: apply more")


# ── App loop ──────────────────────────────────────────────────────────────────

view          = VIEW_DEFAULT
_last_n       = 0
_needs_redraw = True


def update():
    global view, _last_n, _needs_redraw, _pending_card

    badge.default_clear = None

    if badge.pressed(BUTTON_B):
        # Apply: snapshot baseline, drain queued writes, re-read, count only
        # slots whose (label,url) actually changed. The web app always sends
        # all 8 slots, so a raw write count would be meaningless.
        gc.collect()
        old_urls   = _load_list(URLS_PATH, "urls")
        old_topics = _load_list(TOPICS_PATH, "topics")
        old_card   = _read_text(CARD_PATH)

        while _pending_url_items:
            _save_item(URLS_PATH, "urls", _pending_url_items.pop(0))
        if _pending_card is not None:
            raw, _pending_card = _pending_card, None
            _save_raw(CARD_PATH, raw)
        while _pending_topic_items:
            _save_item(TOPICS_PATH, "topics", _pending_topic_items.pop(0))

        if _ble:
            _expose(_url_handle, URLS_PATH, URLS_SEED)
            _expose(_card_handle, *_CARD_READ_PATHS)
            _expose(_topics_handle, TOPICS_PATH)

        new_urls   = _load_list(URLS_PATH, "urls")
        new_topics = _load_list(TOPICS_PATH, "topics")
        new_card   = _read_text(CARD_PATH)

        n = 0
        for i in range(8):
            if old_urls[i] != new_urls[i]:
                n += 1
            if old_topics[i] != new_topics[i]:
                n += 1
        if _card_changed(old_card, new_card):
            n += 1

        _last_n = n
        view = VIEW_COMMITTED
        _needs_redraw = True

    elif view == VIEW_COMMITTED and (badge.pressed(BUTTON_UP) or badge.pressed(BUTTON_DOWN)):
        view = VIEW_DEFAULT
        _needs_redraw = True

    if _needs_redraw:
        _needs_redraw = False
        if view == VIEW_COMMITTED:
            draw_committed(_last_n)
        else:
            draw_default()
        badge.update()

    wait_for_button_or_alarm()


def on_exit():
    # HOME closes the app: stop advertising first, then fully power the radio
    # down (user wants Bluetooth off whenever Settings isn't open).
    try:
        if _ble:
            _stop_advertising()
            _ble.active(False)
    except Exception:
        pass


run(update)
