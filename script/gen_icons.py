#!/usr/bin/env python3
"""Generate placeholder PNG icons for new BadgeOS apps.

Usage: python3 script/gen_icons.py

Requires Pillow: pip install Pillow
Output: badger_os/examples/icon-{card,url-share,schedule}.png (128x128 monochrome)
"""
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Install Pillow first: pip install Pillow")
    raise SystemExit(1)

OUT_DIR = Path(__file__).parent.parent / "badger_os" / "examples"
SIZE = (128, 128)
BG = (255, 255, 255)
FG = (0, 0, 0)

ICONS = {
    "icon-card": {
        "emoji": None,
        "lines": ["👤", "CARD"],
        "shapes": "card",
    },
    "icon-url-share": {
        "emoji": None,
        "lines": ["📡", "SHARE"],
        "shapes": "share",
    },
    "icon-schedule": {
        "emoji": None,
        "lines": ["📅", "SCHED"],
        "shapes": "schedule",
    },
}


def make_card_icon(draw):
    # Simple person silhouette + card outline
    draw.rectangle([16, 16, 112, 112], outline=FG, width=4)
    draw.ellipse([44, 28, 84, 62], fill=FG)
    draw.rectangle([24, 68, 104, 104], fill=FG)


def make_share_icon(draw):
    # Simple BLE signal arcs
    cx, cy = 64, 64
    for r in [20, 36, 52]:
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=-60, end=60, fill=FG, width=5)
    draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=FG)


def make_schedule_icon(draw):
    # Calendar grid
    draw.rectangle([16, 24, 112, 112], outline=FG, width=4)
    draw.line([16, 48, 112, 48], fill=FG, width=3)
    draw.rectangle([32, 16, 48, 36], fill=FG)
    draw.rectangle([80, 16, 96, 36], fill=FG)
    # Grid cells
    for row in range(3):
        for col in range(3):
            x = 24 + col * 28
            y = 56 + row * 18
            draw.rectangle([x, y, x + 18, y + 12], outline=FG, width=2)


def make_icon(name, spec):
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    shapefn = {
        "card": make_card_icon,
        "share": make_share_icon,
        "schedule": make_schedule_icon,
    }[spec["shapes"]]
    shapefn(draw)
    path = OUT_DIR / (name + ".png")
    img.save(path)
    print(f"  wrote {path.relative_to(Path.cwd())}")


if __name__ == "__main__":
    print("Generating icons...")
    for name, spec in ICONS.items():
        make_icon(name, spec)
    print("Done.")
