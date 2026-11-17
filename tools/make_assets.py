#!/usr/bin/python3
"""Build brand assets from the Dad's Fixit Shop wallpaper.
usage: make_assets.py WALLPAPER.jpg   (writes into ../data)"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

src = Image.open(sys.argv[1]).convert("RGB")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CX, CY, R = 628, 398, 273          # medallion centre / radius in the source image

# 1. medallion, circular cut-out
med = src.crop((CX - R, CY - R, CX + R, CY + R)).convert("RGBA")
mask = Image.new("L", med.size, 0)
ImageDraw.Draw(mask).ellipse((2, 2, med.width - 3, med.height - 3), fill=255)
med.putalpha(mask)
med.resize((512, 512), Image.LANCZOS).save(f"{out}/brand/dfs-logo.png")

# 2. circuit background tile (strip left of the medallion, mirrored to widen)
strip = src.crop((0, 0, 280, 832)).resize((336, 1000), Image.LANCZOS)   # stays clear of the wallpaper text
bg = Image.new("RGB", (336 * 5, 1000))
for i in range(5):
    bg.paste(strip if i % 2 == 0 else strip.transpose(Image.FLIP_LEFT_RIGHT), (i * 336, 0))
bg = ImageEnhance.Brightness(bg).enhance(0.85)
bg.save(f"{out}/brand/circuit-bg.jpg", quality=82)

# 3. app icon: medallion inside a DiskGlance usage ring on a dark tile
S = 1024
tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
grad = Image.new("RGBA", (S, S))
px = grad.load()
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        px[x, y] = (int(8 + 22 * t), int(12 + 8 * t), int(34 + 40 * t), 255)
rr = Image.new("L", (S, S), 0)
ImageDraw.Draw(rr).rounded_rectangle((24, 24, S - 24, S - 24), 230, fill=255)
tile.paste(grad, (0, 0), rr)
# faint circuit texture
tex = bg.crop((0, 0, 1000, 1000)).resize((S, S)).convert("RGBA")
tex.putalpha(rr.point(lambda v: int(v * 0.22)))
tile.alpha_composite(tex)

ring_r, thick = 424, 46
ring = Image.new("L", (S, S), 0)
d = ImageDraw.Draw(ring)
box = (S / 2 - ring_r, S / 2 - ring_r, S / 2 + ring_r, S / 2 + ring_r)
d.arc(box, -90, -90 + 270, fill=255, width=thick)
for ang in (-90, -90 + 270):       # round caps
    a = math.radians(ang)
    ex, ey = S / 2 + (ring_r - thick / 2) * math.cos(a), S / 2 + (ring_r - thick / 2) * math.sin(a)
    d.ellipse((ex - thick / 2, ey - thick / 2, ex + thick / 2, ey + thick / 2), fill=255)
track = Image.new("L", (S, S), 0)
ImageDraw.Draw(track).ellipse(box, outline=255, width=thick)
tl = Image.new("RGBA", (S, S), (255, 255, 255, 0))
tl.putalpha(track.point(lambda v: int(v * 0.14)))
tile.alpha_composite(tl)
cg = Image.new("RGBA", (S, S)); cp = cg.load()
c1, c2 = (34, 211, 238), (139, 92, 246)
for y in range(S):
    for x in range(S):
        a = (math.degrees(math.atan2(y - S / 2, x - S / 2)) + 90) % 360
        t = min(a / 270, 1.0)
        cp[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)
tile.paste(cg, (0, 0), ring)

m = med.resize((736, 736), Image.LANCZOS)
tile.alpha_composite(m, ((S - 736) // 2, (S - 736) // 2))
for size in (512, 256, 128, 64, 48):
    p = f"{out}/icons/hicolor/{size}x{size}/apps"
    os.makedirs(p, exist_ok=True)
    tile.resize((size, size), Image.LANCZOS).save(f"{p}/io.github.rickbme.DiskGlance.png")
