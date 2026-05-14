"""URL Share via BLE — press A to start advertising, then use the companion web page
(web/index.html) in Chrome to send a URL. The URL and its QR code are displayed.

BLE Service UUID : ba5d4e57-0000-0000-0000-000000000001
URL Char UUID    : ba5d4e57-0000-0000-0000-000000000002

Navigation:
  A          — start BLE advertising (or stop if already advertising)
  B          — return to launcher
  A+C        — return to launcher (standard BadgeOS exit)
"""
import asyncio
import aioble
import bluetooth
import badger2040
import badger_os
import qrcode

WIDTH = badger2040.WIDTH   # 296
HEIGHT = badger2040.HEIGHT  # 128

_SVC_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000001")
_URL_UUID = bluetooth.UUID("ba5d4e57-0000-0000-0000-000000000002")

_svc = aioble.Service(_SVC_UUID)
_url_char = aioble.Characteristic(_svc, _URL_UUID, write=True, read=True, capture=True)
aioble.register_services(_svc)

display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)
display.set_thickness(2)

state = {"url": "", "ble_active": False}
badger_os.state_load("url_share", state)

_exit_app = False


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _measure_qr(size, code):
    w, _ = code.get_size()
    module_size = int(size / w)
    return module_size * w, module_size


def _draw_qr(ox, oy, size, code):
    cell, mod = _measure_qr(size, code)
    display.set_pen(15)
    display.rectangle(ox, oy, cell, cell)
    display.set_pen(0)
    w, h = code.get_size()
    for x in range(w):
        for y in range(h):
            if code.get_module(x, y):
                display.rectangle(ox + x * mod, oy + y * mod, mod, mod)


def draw_idle():
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    display.rectangle(0, 0, WIDTH, 24)
    display.set_pen(15)
    display.set_font("sans")
    display.text("URL Share", 8, 12, 200, 0.55)

    display.set_pen(0)
    display.set_font("sans")
    display.text("Press A to enable BLE", 8, 44, WIDTH - 10, 0.65)
    display.text("then open the companion page", 8, 68, WIDTH - 10, 0.5)
    display.text("in Chrome.", 8, 88, WIDTH - 10, 0.5)

    display.line(0, 108, WIDTH, 108)
    display.set_font("bitmap8")
    display.text("A: start BLE", 8, 116, 140, 1)
    display.text("B: menu", 210, 116, 90, 1)

    display.update()


def draw_advertising():
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    display.rectangle(0, 0, WIDTH, 24)
    display.set_pen(15)
    display.set_font("sans")
    display.text("BLE Active", 8, 12, 200, 0.55)

    display.set_pen(0)
    display.set_font("sans")
    display.text("Open Chrome → companion page", 8, 44, WIDTH - 10, 0.55)
    display.text("Tap Connect → select Badger-IO", 8, 68, WIDTH - 10, 0.5)
    display.text("Enter URL and tap Send", 8, 88, WIDTH - 10, 0.5)

    display.line(0, 108, WIDTH, 108)
    display.set_font("bitmap8")
    display.text("A: stop BLE", 8, 116, 140, 1)
    display.text("B: menu", 210, 116, 90, 1)

    display.update()


def draw_url(url):
    display.set_pen(15)
    display.clear()
    display.set_pen(0)

    code = qrcode.QRCode()
    code.set_text(url)
    qr_size = min(HEIGHT, 120)
    cell, _ = _measure_qr(qr_size, code)
    qr_y = (HEIGHT - cell) // 2
    _draw_qr(0, qr_y, qr_size, code)

    divider_x = cell + 4
    display.line(divider_x, 0, divider_x, HEIGHT)

    text_x = divider_x + 6
    text_w = WIDTH - text_x - 4

    display.set_font("sans")
    short = url.replace("https://", "").replace("http://", "")
    # Try fitting on two lines with word wrap
    display.text(short, text_x, 20, text_w, 0.5)

    display.line(0, 108, WIDTH, 108)
    display.set_font("bitmap8")
    display.text("A: new URL", text_x, 116, 130, 1)
    display.text("B: menu", 230, 116, 70, 1)

    display.update()


# ---------------------------------------------------------------------------
# Async tasks
# ---------------------------------------------------------------------------

_advertising = False
_connection = None


async def ble_task():
    global _advertising, _connection, state
    while not _exit_app:
        if not _advertising:
            await asyncio.sleep_ms(100)
            continue

        draw_advertising()
        try:
            async with await aioble.advertise(
                250_000,
                name="Badger-IO",
                services=[_SVC_UUID],
            ) as connection:
                _connection = connection
                while connection.is_connected() and _advertising:
                    try:
                        connection, data = await asyncio.wait_for(
                            _url_char.written(), timeout_ms=500
                        )
                        if data:
                            url = bytes(data).decode("utf-8").strip()
                            if url:
                                state["url"] = url
                                badger_os.state_save("url_share", state)
                                _advertising = False
                                draw_url(url)
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            pass
        finally:
            _connection = None
            if _advertising:
                _advertising = False


async def button_task():
    global _advertising, _exit_app
    while not _exit_app:
        display.keepalive()

        if display.pressed(badger2040.BUTTON_A):
            _advertising = not _advertising
            if not _advertising and state["url"]:
                draw_url(state["url"])
            elif not _advertising:
                draw_idle()
            await asyncio.sleep_ms(300)

        if display.pressed(badger2040.BUTTON_B):
            _exit_app = True
            break

        await asyncio.sleep_ms(50)


async def main():
    if state["url"]:
        draw_url(state["url"])
    else:
        draw_idle()

    await asyncio.gather(
        asyncio.create_task(ble_task()),
        asyncio.create_task(button_task()),
    )


asyncio.run(main())

import machine
machine.reset()
