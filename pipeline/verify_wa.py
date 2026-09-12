#!/usr/bin/env python3
"""The gate. Verify WorkAdventure woka textures and their previews.

    python3 pipeline/verify_wa.py characters/*/out/*.png

Checks, per texture:
  format   96x128 RGBA, 4 rows x 3 columns of 32x32
  usage    character >=30px tall in every row (fills the cell like the game's sprites)
  alpha    1-bit — no semi-transparent pixels (they render as haze at 32px)
  palette  <=32 colours
  previews if sibling walk_<dir>.gif / idle_<dir>.png exist, they must be the
           shipped texture's pixels: GIF frames in the engine's [0,1,2,1] order,
           idle stills equal to column 1

Exits non-zero if anything fails, so CI can gate on it.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

from PIL import Image, ImageSequence

warnings.filterwarnings("ignore", category=DeprecationWarning)

ORDER = ["down", "left", "right", "up"]
WALK_SEQ = [0, 1, 2, 1]
MIN_HEIGHT = 30          # the game's own wokas are 31-32
MAX_COLORS = 32


def is_texture(p: Path) -> bool:
    """A woka texture is the 96x128 PNG named after its character directory."""
    try:
        return Image.open(p).size == (96, 128)
    except Exception:
        return False


def check(texture: Path) -> list[str]:
    fails: list[str] = []
    im = Image.open(texture)
    if im.format != "PNG":
        fails.append(f"not a PNG ({im.format})")
    im = im.convert("RGBA")
    if im.size != (96, 128):
        fails.append(f"size is {im.size}, must be (96, 128)")
        return fails

    soft = sum(1 for p in im.getdata() if 0 < p[3] < 255)
    if soft:
        fails.append(f"{soft} semi-transparent pixels (harden alpha to 1-bit)")

    opaque = [p for p in im.getdata() if p[3] >= 128]
    colours = len({p[:3] for p in opaque})
    if colours > MAX_COLORS:
        fails.append(f"{colours} colours (keep <= {MAX_COLORS})")
    if not opaque:
        fails.append("texture is fully transparent")
        return fails

    for i, d in enumerate(ORDER):
        cell = im.crop((32, i * 32, 64, i * 32 + 32))
        bb = cell.getchannel("A").getbbox()
        h = (bb[3] - bb[1]) if bb else 0
        if h < MIN_HEIGHT:
            fails.append(f"row {i} ({d}) character is {h}px tall "
                         f"(min {MIN_HEIGHT} — it will look tiny in game)")

        gif = texture.parent / f"walk_{d}.gif"
        if gif.exists():
            got = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(gif))]
            exp = [im.crop((c * 32, i * 32, (c + 1) * 32, (i + 1) * 32)) for c in WALK_SEQ]
            # previews are upscaled; compare at the preview's scale
            if got and got[0].size != exp[0].size:
                exp = [e.resize(got[0].size, Image.NEAREST) for e in exp]
            if len(got) != len(exp):
                fails.append(f"walk_{d}.gif has {len(got)} frames, expected {len(exp)}")
            else:
                bad = sum(1 for a, b in zip(exp, got)
                          for pa, pb in zip(a.getdata(), b.getdata())
                          if (pa[3] >= 128 or pb[3] >= 128) and pa != pb)
                if bad:
                    fails.append(f"walk_{d}.gif differs from the texture in {bad} pixels")

        still = texture.parent / f"idle_{d}.png"
        if still.exists():
            s = Image.open(still).convert("RGBA")
            exp = im.crop((32, i * 32, 64, i * 32 + 32))
            exp = exp.resize(s.size, Image.NEAREST)
            if any(pa != pb for pa, pb in zip(s.getdata(), exp.getdata())
                   if pa[3] >= 128 or pb[3] >= 128):
                fails.append(f"idle_{d}.png is not column 1 of the texture")
    return fails


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    ok = True
    for arg in argv:
        p = Path(arg)
        if not p.exists():
            print(f"FAIL {arg}: not found")
            ok = False
            continue
        if not is_texture(p):
            print(f"SKIP {p} (not a 96x128 woka texture — previews are checked via their texture)")
            continue
        fails = check(p)
        if fails:
            ok = False
            print(f"FAIL {p}")
            for f in fails:
                print(f"     - {f}")
        else:
            im = Image.open(p).convert("RGBA")
            heights = []
            for i in range(4):
                bb = im.crop((32, i * 32, 64, i * 32 + 32)).getchannel("A").getbbox()
                heights.append(bb[3] - bb[1] if bb else 0)
            widths = []
            for i in range(4):
                bb = im.crop((32, i * 32, 64, i * 32 + 32)).getchannel("A").getbbox()
                widths.append((bb[2] - bb[0]) if bb else 0)
            print(f"PASS {p}  heights={heights}  widths={widths}")
    print("ALL PASS" if ok else "FAILURES — see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
