#!/usr/bin/env python3
"""Measure textures against each other and (optionally) against a reference.

    python3 pipeline/compare_wa.py characters/*/out/*.png \
        --reference-dir /path/to/workadventure-universe/play/public/resources/characters/pipoya

Prints the numbers that decide whether a sprite looks the right size in game,
and writes compare.png next to the first texture. Per 32px cell, down-facing row,
middle frame: height, width, ink pixels, colours.

The game's own wokas measure 32 tall / 23-27 wide / ~600 ink / 29-41 colours.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

UPSCALE = 8
CELL = 32


def measure(im: Image.Image) -> dict:
    c = im.crop((CELL, 0, 2 * CELL, CELL)).convert("RGBA")
    bb = c.getchannel("A").getbbox() or (0, 0, 0, 0)
    op = [p for p in c.getdata() if p[3] >= 128]
    return {"h": bb[3] - bb[1], "w": bb[2] - bb[0], "ink": len(op),
            "cell_colours": len({p[:3] for p in op}),
            "sheet_colours": len({p[:3] for p in im.getdata() if p[3] >= 128}),
            "soft": sum(1 for p in im.getdata() if 0 < p[3] < 255)}


def label(d: ImageDraw.ImageDraw, xy, text: str, size: int = 18) -> None:
    f = None
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        if Path(p).exists():
            f = ImageFont.truetype(p, size)
            break
    d.text(xy, text, fill=(235, 235, 245, 255), font=f or ImageFont.load_default())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("textures", nargs="+", type=Path)
    ap.add_argument("--reference-dir", type=Path, default=None,
                    help="directory of reference spritesheets (96x128)")
    ap.add_argument("--out", type=Path, default=None, help="where to write compare.png")
    args = ap.parse_args()

    entries: list[tuple[str, Image.Image]] = []
    if args.reference_dir and args.reference_dir.is_dir():
        # prefer human references; fall back to whatever is there
        preferred = ["Male 01-1.png", "Female 01-1.png", "Male 09-1.png"]
        picks = [args.reference_dir / n for n in preferred]
        picks = [p for p in picks if p.exists()]
        if not picks:
            picks = sorted(args.reference_dir.glob("*.png"))[:3]
        for p in picks:
            im = Image.open(p).convert("RGBA")
            if im.size == (96, 128):
                entries.append((f"{p.stem}", im))
    ref_count = len(entries)
    for p in args.textures:
        im = Image.open(p).convert("RGBA")
        if im.size != (96, 128):
            print(f"skip {p}: size {im.size}, not a 96x128 texture")
            continue
        entries.append((p.parent.parent.name if p.parent.name == "out" else p.stem, im))

    if not entries:
        print("nothing to compare")
        return 1

    print(f"{'texture':26s} {'height':>7s} {'width':>6s} {'ink':>6s} {'cellCols':>9s} "
          f"{'sheetCols':>10s} {'softAlpha':>10s}")
    for name, im in entries:
        m = measure(im)
        tag = "reference" if entries.index((name, im)) < ref_count else ""
        print(f"{name:26s} {m['h']:>7d} {m['w']:>6d} {m['ink']:>6d} {m['cell_colours']:>9d} "
              f"{m['sheet_colours']:>10d} {m['soft']:>10d}  {tag}")

    blocks = [(n, im.resize((im.width * UPSCALE, im.height * UPSCALE), Image.NEAREST))
              for n, im in entries]
    pad, gap, top = 90, 20, 30
    W = pad + sum(b.width for _, b in blocks) + gap * (len(blocks) - 1) + 20
    H = top + max(b.height for _, b in blocks) + 24
    canvas = Image.new("RGBA", (W, H), (24, 24, 28, 255))
    dr = ImageDraw.Draw(canvas)
    x = 12
    for name, b in blocks:
        canvas.alpha_composite(b, (x, top))
        for i, line in enumerate(name.split("_")):
            label(dr, (x, top - 26 + i * 18), line)
        x += b.width + gap
    out = args.out or (args.textures[0].parent / "compare.png")
    canvas.convert("RGB").save(out)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
