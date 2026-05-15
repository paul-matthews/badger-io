#!/usr/bin/env python3
"""Generate apps/settings/icon.png — a 24x24 RGBA cog/gear.

Matches the sibling app icons: transparent background, solid black shape,
supersampled then downscaled for clean edges.

Usage: python3 script/gen_settings_icon.py
Requires Pillow: pip install Pillow
"""
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Install Pillow first: pip install Pillow")
    raise SystemExit(1)

OUT = Path(__file__).parent.parent / "apps" / "settings" / "icon.png"
SIZE = 24
S = 16                       # supersample factor
N = 24 * S
C = N / 2.0

TEETH = 8
R_TIP = 0.95 * C             # tooth tip radius
R_BODY = 0.66 * C            # gear disc radius
R_HOLE = 0.30 * C            # centre hole radius
TOOTH_HALF_DEG = 13.0        # angular half-width of each tooth at its base


def _pt(angle_deg, r):
    a = math.radians(angle_deg)
    return (C + r * math.cos(a), C + r * math.sin(a))


mask = Image.new("L", (N, N), 0)
d = ImageDraw.Draw(mask)

# Gear disc.
d.ellipse([C - R_BODY, C - R_BODY, C + R_BODY, C + R_BODY], fill=255)

# Teeth: slightly tapered trapezoids from the disc edge out to the tip.
for i in range(TEETH):
    base = i * (360.0 / TEETH)
    poly = [
        _pt(base - TOOTH_HALF_DEG, R_BODY - 2),
        _pt(base + TOOTH_HALF_DEG, R_BODY - 2),
        _pt(base + TOOTH_HALF_DEG * 0.6, R_TIP),
        _pt(base - TOOTH_HALF_DEG * 0.6, R_TIP),
    ]
    d.polygon(poly, fill=255)

# Punch the centre hole back to transparent.
d.ellipse([C - R_HOLE, C - R_HOLE, C + R_HOLE, C + R_HOLE], fill=0)

# Compose solid black with the mask as alpha, then downscale.
icon = Image.new("RGBA", (N, N), (0, 0, 0, 0))
black = Image.new("RGBA", (N, N), (0, 0, 0, 255))
icon = Image.composite(black, icon, mask)
icon = icon.resize((SIZE, SIZE), Image.LANCZOS)

OUT.parent.mkdir(parents=True, exist_ok=True)
icon.save(OUT)
print(f"wrote {OUT}")
