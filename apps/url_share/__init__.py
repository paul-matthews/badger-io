import sys
import os
import bluetooth
import qrcode
from badgeware import run, State

sys.path.insert(0, "/system/apps/url_share")
os.chdir("/system/apps/url_share")

COMPANION_URL = "https://paul-matthews.github.io/badger-io/"

small = rom_font.smart
W = screen.width
H = screen.height
FOOTER_LINE_Y = H - 18
FOOTER_TEXT_Y = H - 12

state = {"url": ""}
State.load("url_share", state)

_companion_code = qrcode.QRCode()
_companion_code.set_text(COMPANION_URL)

# ── BLE ───────────────────────────────────────────────────────────────────────

_SVC_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000001")
_URL_UUID  = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000002")

_FLAG_READ  = 0x0002
_FLAG_WRITE = 0x0008

_ble = bluetooth.BLE()
_ble.active(True)

_pending_url = None
_url_handle  = None


def _ble_irq(event, data):
    global _pending_url
    if event == 3:  # IRQ_GATTS_WRITE
        conn_handle, attr_handle = data
        if attr_handle == _url_handle:
            _pending_url = _ble.gatts_read(_url_handle).decode("utf-8").strip()


_ble.irq(_ble_irq)
((_url_handle,),) = _ble.gatts_register_services((
    (_SVC_UUID, ((_URL_UUID, _FLAG_READ | _FLAG_WRITE),)),
))

# Advertising: flags + 128-bit UUID in adv_data; name in scan response
_adv_data  = b'\x02\x01\x06' + bytes([0x11, 0x07]) + bytes(_SVC_UUID)
_resp_data = bytes([0x0a, 0x09]) + b'Badger-IO'


def _start_advertising():
    _ble.gap_advertise(100_000, adv_data=_adv_data, resp_data=_resp_data)


def _stop_advertising():
    _ble.gap_advertise(None)


# ── Drawing ───────────────────────────────────────────────────────────────────

def _header(label):
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, 26))
    screen.pen = color.white
    screen.font = small
    screen.text(label, 8, 8)


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


def draw_idle():
    screen.pen = color.white
    screen.clear()
    _header("URL Share")
    screen.pen = color.black
    screen.font = small
    screen.text("Press B to start sharing.", 8, 52)
    screen.text("BLE is off.", 8, 68)
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.text("B: start", 8, FOOTER_TEXT_Y)
    hw, _ = screen.measure_text("HOME: menu")
    screen.text("HOME: menu", W - hw - 8, FOOTER_TEXT_Y)


def draw_advertising():
    print("url_share: draw_adv: clear")
    screen.pen = color.white
    screen.clear()
    print("url_share: draw_adv: header")
    _header("Sharing - scan QR to connect")
    print("url_share: draw_adv: qr start")
    try:
        qr_total = _draw_qr(4, 30, _companion_code)
        print("url_share: draw_adv: qr done, size", qr_total)
    except Exception as e:
        print("url_share: draw_adv: qr FAIL", type(e).__name__, str(e))
        return
    tx = qr_total + 12
    print("url_share: draw_adv: text")
    screen.pen = color.black
    screen.font = small
    screen.text("Open in Chrome,", tx, 38)
    screen.text("tap Connect,", tx, 54)
    screen.text("enter a URL", tx, 70)
    screen.text("and tap Send.", tx, 86)
    print("url_share: draw_adv: footer")
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.text("B: stop", 8, FOOTER_TEXT_Y)
    hw, _ = screen.measure_text("HOME: menu")
    screen.text("HOME: menu", W - hw - 8, FOOTER_TEXT_Y)
    print("url_share: draw_adv: done")


def draw_url(url):
    screen.pen = color.white
    screen.clear()
    _header("Received")

    code = qrcode.QRCode()
    code.set_text(url)
    qr_total = _draw_qr(4, 30, code)

    tx = qr_total + 12
    screen.pen = color.black
    screen.font = small
    short = url.replace("https://", "").replace("http://", "")
    screen.text(short, tx, 38)

    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, FOOTER_LINE_Y, W, 1))
    screen.text("B: back", 8, FOOTER_TEXT_Y)
    hw, _ = screen.measure_text("HOME: menu")
    screen.text("HOME: menu", W - hw - 8, FOOTER_TEXT_Y)


# ── App loop ──────────────────────────────────────────────────────────────────

_ble_active   = False
_last_a       = False
_needs_redraw = True
_ticks        = 0


def init():
    pass


def update():
    global _ble_active, _last_a, _needs_redraw, _pending_url, _ticks
    _ticks += 1
    if _ticks <= 5 or _ticks % 30 == 0:
        print("url_share: tick", _ticks, "ble:", _ble_active)

    b_now = io.BUTTON_B in io.pressed

    if _pending_url is not None:
        url = _pending_url
        _pending_url = None
        _ble_active = False
        _stop_advertising()
        state["url"] = url
        State.modify("url_share", state)
        draw_url(url)

    elif b_now and not _last_a:
        if state["url"]:
            state["url"] = ""
            State.modify("url_share", state)
            draw_idle()
        else:
            _ble_active = not _ble_active
            if _ble_active:
                print("url_share: B pressed - starting adv")
                try:
                    _start_advertising()
                    print("url_share: gap_advertise ok")
                except Exception as e:
                    print("url_share: gap_advertise FAIL", type(e).__name__, str(e))
                    _ble_active = False
                print("url_share: drawing adv screen")
                draw_advertising()
                print("url_share: draw_advertising returned")
            else:
                _stop_advertising()
                draw_idle()
        _needs_redraw = False

    elif _needs_redraw:
        if state["url"]:
            draw_url(state["url"])
        else:
            draw_idle()
        _needs_redraw = False

    _last_a = b_now


def on_exit():
    if _ble_active:
        _stop_advertising()


if __name__ == "__main__":
    run(update)
