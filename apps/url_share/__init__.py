import sys
import os
import asyncio
import aioble
import bluetooth
import qrcode
from badgeware import State

sys.path.insert(0, "/system/apps/url_share")
os.chdir("/system/apps/url_share")

_SVC_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000001")
_URL_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000002")

_svc = aioble.Service(_SVC_UUID)
_url_char = aioble.Characteristic(_svc, _URL_UUID, write=True, read=True, capture=True)
aioble.register_services(_svc)

state = {"url": ""}
State.load("url_share", state)

small = rom_font.smart
W = screen.width
H = screen.height


def _header(label):
    screen.pen = color.black
    screen.shape(shape.rectangle(0, 0, W, 26))
    screen.pen = color.white
    screen.font = small
    screen.text(label, 8, 8)


def _draw_qr(ox, oy, code):
    w, _ = code.get_size()
    cell_size = max(1, min(H - 36, 90) // w)
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
    screen.text("Press A to enable BLE,", 8, 38)
    screen.text("then open the companion", 8, 54)
    screen.text("page in Chrome.", 8, 70)
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, 110, W, 1))
    screen.text("A: start BLE", 8, 116)


def draw_advertising():
    screen.pen = color.white
    screen.clear()
    _header("BLE Active")
    screen.pen = color.black
    screen.font = small
    screen.text("Open Chrome companion page,", 8, 38)
    screen.text("tap Connect → Badger-IO,", 8, 54)
    screen.text("enter URL and tap Send.", 8, 70)
    screen.pen = color.dark_grey
    screen.shape(shape.rectangle(0, 110, W, 1))
    screen.text("A: stop BLE", 8, 116)


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
    screen.shape(shape.rectangle(0, 110, W, 1))
    screen.text("A: clear  HOME: menu", 8, 116)


_ble_active = False
_done = False


async def _ble_task():
    global _ble_active, state
    while not _done:
        if not _ble_active:
            await asyncio.sleep_ms(100)
            continue

        draw_advertising()
        try:
            async with await aioble.advertise(
                250_000,
                name="Badger-IO",
                services=[_SVC_UUID],
            ) as connection:
                while connection.is_connected() and _ble_active:
                    try:
                        _, data = await asyncio.wait_for_ms(
                            _url_char.written(), timeout_ms=500
                        )
                        if data:
                            url = bytes(data).decode("utf-8").strip()
                            if url:
                                state["url"] = url
                                State.modify("url_share", state)
                                _ble_active = False
                                draw_url(url)
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            pass


async def _input_task():
    global _ble_active, _done, state
    _last_a = False

    if state["url"]:
        draw_url(state["url"])
    else:
        draw_idle()

    while not _done:
        a_now = io.BUTTON_A in io.pressed
        if a_now and not _last_a:
            if state["url"]:
                state["url"] = ""
                State.modify("url_share", state)
                draw_idle()
            else:
                _ble_active = not _ble_active
                if not _ble_active:
                    draw_idle()
        _last_a = a_now
        await asyncio.sleep_ms(50)


def init():
    pass


def on_exit():
    global _done
    _done = True


asyncio.run(asyncio.gather(
    asyncio.create_task(_ble_task()),
    asyncio.create_task(_input_task()),
))
