# Badgeware API Reference — Badger 2350 W

Source: `github.com/pimoroni/badgeware-docs` + `pimoroni/badger2350` source.
Firmware: `bw-1.27.0` / pimoroni-badger2350 v1.0.0.

---

## Display

**Resolution: 264 × 176 pixels**, 4 shades of grey (e-paper).

`screen` is an `image` object backed by the display framebuffer. It is a **frozen global** — available after `import badgeware` but NOT as `badgeware.screen`. Access it directly as `screen`.

```python
screen.width   # 264
screen.height  # 176
```

---

## App structure

```python
# __init__.py

def init():          # optional — called once on launch
    pass

def update():        # required — called every frame/wake
    screen.pen = color.navy
    screen.clear()
    screen.pen = color.white
    screen.font = rom_font.smart
    screen.text("Hello!", 10, 50)

def on_exit():       # optional — called when HOME pressed
    pass

run(update)          # REQUIRED at end of module
```

### Lifecycle (Badger e-paper specifics)

- Badger **sleeps between updates** to save power. On wake, the program restarts from scratch — `init()` runs again, RAM is cleared.
- Use `State.save/load` to persist data across sleep cycles.
- `wait_for_button_or_alarm()` is the correct idle pattern — it sleeps the device.
- The HOME button triggers `on_exit()` then returns to menu (handled by firmware IRQ).
- `/system/` is **read-only** at runtime. Write to `/state/` or `/` (LittleFS root).

### Entry point rule

`/system/main.py` imports the app with `__import__(app)`, and the app **blocks during import** by calling `run(update)` at module level. `main.py` does NOT call `run()` itself after the import.

Use this guard to prevent double-execution when imported as a module (e.g. during testing):

```python
if __name__ == "__main__":
    run(update)
```

But for normal deployment via the menu, `run(update)` at module level is the correct pattern per the official docs.

---

## Frozen globals (available without import)

| Global | Type | Description |
|--------|------|-------------|
| `screen` | `image` | Display framebuffer, 264×176 |
| `badge` | `Badge` | Hardware access |
| `color` | module | Color creation + named palette |
| `brush` | module | Pattern/image brushes |
| `image` | type | Image/canvas type |
| `shape` | type | Vector shape primitives |
| `rom_font` | `ROMFonts` | Access built-in pixel fonts |
| `text` | `_text` | Advanced text (wrap, scroll) |
| `rect` | type | Rectangle type |
| `vec2` | type | 2D vector/point type |
| `mat3` | type | 2D transformation matrix |
| `State` | class | JSON state persistence |
| `rtc` | `RTC` | Real-time clock |
| `run` | callable | App event loop |
| `launch` | fn | Launch another app by path |
| `loop` | `_run` | Current running loop (or None) |
| `reset` | fn | Safe soft reset |
| `wait_for_button_or_alarm` | fn | Sleep until input or alarm |
| `fatal_error` | fn | Show error overlay + reset |
| `file_exists` | fn | Check if path exists |
| `is_dir` | fn | Check if path is directory |
| `free` | fn | Print free RAM to console |
| `clamp` | fn | `clamp(v, min, max)` |
| `rnd` | fn | `rnd(max)` or `rnd(min, max)` — int random |
| `frnd` | fn | `frnd(max)` or `frnd(min, max)` — float random |

Also hoisted from picovector: `font`, `pixel_font`, `OFF`, `X2`, `X4`.

**Import pattern:** `from badgeware import run, State` — `run` and `State` are importable. Other globals are builtins and need no import.

---

## `badge` — Hardware

```python
# Properties (read-only)
badge.ticks          # ms since power-on at last update()
badge.ticks_delta    # ms since previous update() — use for animation timing
badge.uid            # unique device ID (hex string)
badge.resolution     # (264, 176) tuple

# Mutable properties
badge.default_clear  # color | None — screen clear color each frame (None = no clear)
badge.default_pen    # color — default pen after clear
badge.update         # reassign to swap screen handler

# Buttons
badge.pressed(BUTTON_A)    # True on first frame button is pressed
badge.held(BUTTON_B)       # True continuously while held
badge.released(BUTTON_C)   # True on first frame button is released
badge.changed(BUTTON_UP)   # True if state changed this frame
badge.pressed()            # returns list of all currently-pressed buttons
```

### Button constants
```
BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_UP, BUTTON_DOWN, BUTTON_HOME
```

### Display modes (Badger)
```python
badge.mode(FAST_UPDATE)    # fastest, may ghost
badge.mode(MEDIUM_UPDATE)  # balanced — good default
badge.mode(FULL_UPDATE)    # slowest, cleanest
badge.mode(DITHER)         # apply dither each frame automatically
badge.mode(FAST_UPDATE | DITHER)  # combine with pipe
badge.mode(NON_BLOCKING)   # non-blocking display update
```

`LORES` / `HIRES` / `VSYNC` flags are **Tufty only** — no effect on Badger.

### Battery & power
```python
badge.battery_level()    # 0-100 int
badge.battery_voltage()  # float volts
badge.usb_connected()    # bool
badge.is_charging()      # bool
badge.sleep()            # sleep indefinitely (woken by button or alarm)
badge.sleep(seconds)     # sleep for N seconds
badge.woken_by_button()  # bool
badge.woken_by_reset()   # bool
```

### Rear LEDs (4 LEDs on back)
```python
badge.caselights(0.5)                  # all at 50%
badge.caselights(1.0, 0.5, 0.0, 0.5)  # individual values 0-1
badge.caselights()                     # returns current values as list
```

### Misc
```python
badge.disk_free()              # (total, used, free) bytes at /system
badge.disk_free("/")           # for another mountpoint
badge.poll()                   # update button state (auto-called by run())
badge.update()                 # screen.update() + badge.clear() + badge.poll()
```

---

## `screen` / `image` — Drawing

`screen` is the main drawing surface. All `image` methods also apply to off-screen images.

### Properties
```python
screen.width      # 264 (Badger)
screen.height     # 176 (Badger)
screen.pen        # current color or brush for drawing
screen.font       # current pixel_font or vector font
screen.clip       # current clipping rect
screen.antialias  # image.OFF | image.X2 | image.X4
screen.alpha      # 0-255 global alpha for drawing ops
```

### Creating/loading images
```python
img = image(w, h)                    # new blank image
img = image.load("assets/foo.png")   # load PNG or JPEG
```

### Drawing primitives
All use current `screen.pen`.
```python
screen.clear()                          # fill with current pen
screen.put(x, y)                        # single pixel
screen.get(x, y)                        # returns color of pixel
screen.line(x0, y0, x1, y1)
screen.line(vec2(x0, y0), vec2(x1, y1))
screen.rectangle(x, y, w, h)
screen.rectangle(rect(x, y, w, h))
screen.circle(x, y, radius)
screen.circle(vec2(x, y), radius)
screen.triangle(x0, y0, x1, y1, x2, y2)
screen.triangle(vec2(a), vec2(b), vec2(c))
screen.shape(s)                         # draw a vector shape
```

### Text
```python
screen.font = rom_font.sins             # set font first
screen.text("Hello", x, y)             # draw text at (x, y) top-left
screen.text("Hello", vec2(x, y))
w, h = screen.measure_text("Hello")    # measure before drawing to centre
```

**IMPORTANT:** Font renderer crashes on non-ASCII characters. Use ASCII only — no em-dashes, smart quotes, etc.

### Image blitting
```python
screen.blit(img, x, y)                           # 1:1 blit
screen.blit(img, vec2(x, y))
screen.blit(img, rect(x, y, w, h))              # scale to fit rect
screen.blit(img, src_rect, dst_rect)             # crop + scale
# Negative w/h in dest rect = flip horizontally/vertically
```

### Filters (applied to clip area)
```python
screen.blur(radius)   # gaussian blur
screen.dither()       # ordered dither -- useful for Badger grey levels
screen.onebit()       # reduce to black/white
screen.monochrome()   # reduce to greyscale
```

### Sub-views
```python
w = screen.window(x, y, w, h)  # returns image view sharing the buffer
w = screen.window(r)           # from a rect
# Drawing to window is clipped to its area; (0,0) is window's top-left
```

**Do NOT call `screen.update()` from user code** — `run()` handles this automatically.

---

## `color` — Colors

```python
color.rgb(r, g, b)        # 0-255 each
color.rgb(r, g, b, a)     # with alpha
color.hsv(h, s, v)        # 0-255 each
color.oklch(l, c, h)      # perceptually uniform, best for gradients
```

### Named palette (DawnBringer 16)
```python
color.black    # #141e28
color.grape    # #442434
color.navy     # #30346d
color.grey     # #4e4a4e
color.brown    # #854c30
color.green    # #346524
color.red      # #d04648
color.taupe    # #757161
color.blue     # #597dce
color.orange   # #d27d2c
color.smoke    # #8595a1
color.lime     # #6daa2c
color.latte    # #d2aa99
color.cyan     # #6dc2ca
color.yellow   # #dad45e
color.white    # #deeed6
```
Also `color.dark_grey` — used in firmware (error overlay), not in docs but valid.

---

## `brush` — Brushes

```python
# Image brush -- fill shape with image
screen.pen = brush.image(img, mat3().translate(x, y))

# Pattern brush -- fill shape with tiled pattern
screen.pen = brush.pattern(color.white, color.black, 11)  # built-in pattern 0-37
screen.pen = brush.pattern(fg, bg, (                      # custom 8-row binary pattern
    0b01111110,
    0b01000010,
    0b01000010,
    0b01111110,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
))
```

---

## `shape` — Vector shapes

All constructors are static methods returning a `shape`. Draw with `screen.shape(s)`.

```python
shape.circle(x, y, r)
shape.rectangle(x, y, w, h)
shape.rounded_rectangle(x, y, w, h, r)             # single corner radius
shape.rounded_rectangle(x, y, w, h, r1, r2, r3, r4)  # per-corner (TL,TR,BR,BL)
shape.squircle(x, y, size, n=4)                    # n controls squareness
shape.arc(x, y, inner, outer, from_deg, to_deg)    # 0deg = up, clockwise
shape.pie(x, y, r, from_deg, to_deg)
shape.star(x, y, points, outer_r, inner_r)
shape.line(x1, y1, x2, y2, width)
shape.regular_polygon(x, y, r, sides)              # sides >= 3
shape.custom(path1_list, path2_list, ...)           # lists of vec2 or (x,y) tuples
```

### Shape properties & methods
```python
s.transform = mat3().translate(80, 60).rotate(45)  # apply at render time
s.stroke(thickness)   # returns new stroked shape (positive=outward, negative=inward)
```

### Antialiasing
```python
screen.antialias = image.X4    # best quality, slowest
screen.antialias = image.X2    # good quality
screen.antialias = image.OFF   # none (default)
```

---

## `vec2` / `rect` / `mat3` — Geometry types

```python
p = vec2(x, y)         # p.x, p.y  (floats)
p += vec2(dx, dy)      # arithmetic works
p.transform(m)         # returns transformed vec2

r = rect(x, y, w, h)  # r.x, r.y, r.w, r.h
                       # also: r.l (=x), r.r (=x+w), r.t (=y), r.b (=y+h)
r.offset(x, y)         # returns shifted rect
r.deflate(amount)      # returns smaller rect (shrinks all sides)
r.deflate(t, r, b, l)  # per-side shrink
r.inflate(amount)      # returns larger rect
r.intersection(other)  # returns rect or None
r.intersects(other)    # bool
r.contains(other)      # bool
r.empty()              # bool (w or h is zero)

m = mat3()             # identity matrix
m.translate(x, y)      # returns new mat3
m.rotate(degrees)      # returns new mat3
m.rotate_radians(rad)
m.scale(x, y)
m.multiply(other)
m.inverse()
# Chain: mat3().translate(80, 60).rotate(45).scale(2, 2)
```

---

## `rom_font` / `pixel_font` / `font` — Fonts

```python
screen.font = rom_font.sins      # access any ROM font by name
f = pixel_font.load("/system/assets/fonts/unfair.ppf")
screen.font = f
f.height   # font height in pixels
f.name     # font name

# Vector fonts (.af format) -- scalable
vf = font.load("/path/to/font.af")
screen.font = vf
screen.text("Hello", x, y, size=24)         # size required for vector fonts
w, h = screen.measure_text("Hello", size=24)
```

### Available ROM fonts (pixel fonts, .ppf)

| Name | Height | Style |
|------|--------|-------|
| ark | 6px | tiny, smallcaps |
| desert | 6px | tiny, drowsy |
| torch | 6px | fantasy, pocket-sized |
| sins | 7px | tiny, classic, stylish -- **system default** |
| teatime | 7px | classic, readable, monospace |
| hungry | 7px | playful, monospace |
| kobold | 7px | classic, fantasy |
| lookout | 7px | adventurous, fantasy |
| loser | 7px | slanted, smallcaps, monospace |
| winds | 7px | tiny, extra-spaced |
| match | 7px | classic, joyful |
| corset | 8px | elegant, cozy |
| nope | 8px | clear, readable |
| unfair | 8px | wide, retro |
| saga | 8px | medieval, fantasy |
| memo | 9px | wacky, distinctive |
| outflank | 9px | fantasy, arcane |
| salty | 9px | thick, all-purpose |
| smart | 9px | classic, chunky, smallcaps |
| awesome | 9px | cheerful, wholesome |
| compass | 9px | classic, fantasy |
| yolk | 9px | classic, fantasy |
| vest | 9px | elegant, serif |
| holotype | 9px | distinctive, premium |
| yesterday | 10px | bold, readable |
| absolute | 10px | bold, boxy |
| fear | 11px | smallcaps, horror |
| troll | 12px | fantasy, ornate |
| bacteria | 12px | rational, wide, monospace |
| curse | 12px | comic, horror |
| ziplock | 13px | round, cheerful |
| futile | 14px | big, bold, unique |
| manticore | 14px | strong, metal |
| more | 15px | chunky, comic |
| ignore | 17px | colossal |

Also `rom_font.badgeware`, `rom_font.badgewaremax`, `rom_font.nope` used in system UI.

---

## `text` — Advanced text

```python
# Word-wrapped text in a bounding box
screen.font = rom_font.sins
text.draw(screen, "Long message here...", bounds=rect(10, 10, 244, 156))
text.draw(screen, msg, bounds=r, line_spacing=1, word_spacing=1, size=24)

# Tokenise once, draw many times
tokens = text.tokenise(screen, message)
text.draw(screen, tokens, bounds=r)

# Inline color change in string: "[pen:r,g,b]"
text.draw(screen, "Normal [pen:255,0,0]then red", bounds=r)

# Scrolling text -- returns a closure to call each update()
scroll_fn = text.scroll("Long text...", font_face=rom_font.sins, speed=25)
scroll_fn = text.scroll(msg, target=screen.window(5, 5, 254, 30), gap=20, align="middle")
# call every update():
progress = scroll_fn()   # returns 0.0-1.0 progress through cycle
```

---

## `State` — Persistence

```python
state = {"score": 0, "level": 1}   # define defaults
State.load("myapp", state)          # merges /state/myapp.json into dict, or creates it

State.save("myapp", state)          # write dict to /state/myapp.json
State.modify("myapp", {"score": 5}) # load + update + save
State.delete("myapp")               # remove save file
```

**Save all needed data before sleep — RAM is wiped on wake.**

---

## `rtc` — Real-time clock

```python
year, month, day, hour, min, sec, dow = rtc.datetime()
rtc.datetime((2026, 5, 15, 14, 30, 0, 4))  # set datetime (dow=4 = Friday)

rtc.time_from_ntp()           # sync from internet (needs WiFi)
rtc.localtime_to_rtc()        # copy MicroPython localtime to RTC
rtc.rtc_to_localtime()        # copy RTC to MicroPython localtime

rtc.set_alarm(hours=0, minutes=5, seconds=0)  # alarm after 5 min from now
rtc.alarm_status()             # True if alarm interrupt pin is active
rtc.clear_alarm()              # disable alarm interrupts + clear flag

# Typical sleep-and-wake pattern:
rtc.set_alarm(minutes=30)
badge.sleep()                  # wakes after 30 min or any button press
```

---

## `SpriteSheet` / `AnimatedSprite`

```python
sheet = SpriteSheet("assets/sprites.png", columns=8, rows=4)
sprite = sheet.sprite(col, row)              # returns image
screen.blit(sprite, x, y)

anim = sheet.animation(x=0, y=0, count=4, horizontal=True)
# or:
anim = AnimatedSprite(sheet, 0, 0, count=4)
frame_img = anim.frame(int(badge.ticks / 100) % anim.count)
screen.blit(frame_img, x, y)
```

---

## `wait_for_button_or_alarm`

```python
wait_for_button_or_alarm()                     # sleep until button or RTC alarm
wait_for_button_or_alarm(timeout=30_000)       # timeout in ms (default 30s)
# Checks badge.usb_connected() -- won't sleep if USB connected
```

---

## `file_exists` / `is_dir`

```python
if file_exists("assets/data.json"):
    ...
if is_dir("assets"):
    ...
```

---

## `free` / `clamp` / `rnd` / `frnd`

```python
free("after load")          # prints "after load: 45kb (+2kb)" to console
clamp(value, 0, 100)        # clamp to range
rnd(10)                     # int 0-10
rnd(5, 10)                  # int 5-10
frnd(1.0)                   # float 0.0-1.0
```

---

## Common patterns

### Centring text
```python
screen.font = rom_font.nope
w, h = screen.measure_text("Hello")
screen.text("Hello", (screen.width - w) // 2, (screen.height - h) // 2)
```

### Multi-screen navigation
```python
PAGE_MAIN, PAGE_DETAIL = 0, 1
page = PAGE_MAIN

def draw_main():
    screen.text("Main page", 10, 10)

def draw_detail():
    screen.text("Detail page", 10, 10)

def update():
    global page
    if badge.pressed(BUTTON_B):
        page = PAGE_DETAIL if page == PAGE_MAIN else PAGE_MAIN
    [draw_main, draw_detail][page]()

run(update)
```

### Badger sleep/wake pattern
```python
state = {"count": 0}

def init():
    State.load("myapp", state)
    if rtc.alarm_status():
        state["count"] += 1

def update():
    screen.pen = color.white
    screen.clear()
    screen.pen = color.black
    screen.font = rom_font.nope
    screen.text(f"Count: {state['count']}", 10, 10)
    State.save("myapp", state)
    rtc.set_alarm(minutes=5)
    wait_for_button_or_alarm()

run(update)
```

### Sub-window layout zones
```python
header = screen.window(0, 0, 264, 30)
body   = screen.window(0, 30, 264, 146)

def update():
    header.pen = color.navy
    header.clear()
    header.pen = color.white
    header.font = rom_font.nope
    header.text("My App", 5, 8)

    body.pen = color.white
    body.clear()
    # draw body content into body window
    body.pen = color.black
    body.text("Content here", 5, 5)
```

---

## Known gotchas

| Issue | Detail |
|-------|--------|
| `screen.update()` | Do NOT call from user code -- `run()` handles it |
| `screen.set_rotation()` | Does NOT exist -- `screen` doesn't support rotation |
| Non-ASCII characters | **Crash the font renderer** -- ASCII only, no em-dashes, smart quotes etc |
| Globals not on module | `screen`, `badge`, `color` etc are builtins -- NOT accessible as `badgeware.screen` |
| `LORES`/`HIRES` | Tufty-only flags -- no effect on Badger |
| First update | Always does FULL_UPDATE on app launch regardless of mode (firmware resets speed after) |
| BLE GATT buffer | Pre-allocate before use: `ble.gatts_write(handle, b'\x00' * 512)` |
| `color.dark_grey` | Exists in firmware source, not in documented palette -- safe to use |
| Sleep resets state | `init()` runs every wake -- all module-level variables re-initialise |
| `/system/` is read-only | Write app data to `/state/` via `State` or raw file writes |
