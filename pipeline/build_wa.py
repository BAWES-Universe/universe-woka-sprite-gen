#!/usr/bin/env python3
"""Compose a WorkAdventure texture + preview GIFs from a sprite-gen directional run.

    python3 pipeline/build_wa.py --run runs/arab_male --out characters/arab_male/out --name arab_male

What it does, in order:
  1. re-extract every frame at the game's native 32x32, cell margin 0 so the
     character fills the cell the way the game's own sprites do
  2. compose the texture: row0 down, row1 left (mirrored side), row2 right, row3 up
  3. harden alpha to 1-bit and quantise to <=32 flat colours
  4. write walk GIFs *by cropping the finished texture*, so previews are exactly
     the pixels the engine plays
  5. write the static idle still per direction (the engine's idle = column 1)
  6. write an 8x preview, a gallery, and copy the run's reports

Requires: Pillow, and SPRITE_GEN_BIN (or sprite-gen on PATH) for step 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ORDER = ["down", "left", "right", "up"]
ROWS = [("down", "down"), ("left", "side"), ("right", "side"), ("up", "up")]
MIRROR = {"left"}
WALK_SEQ = [0, 1, 2, 1]          # Animation.ts, verbatim
COLS = 3
UPSCALE = 8                      # preview zoom
SENTINEL = (255, 0, 255)         # palette index 0 = transparent


def sprite_gen() -> str:
    return os.environ.get("SPRITE_GEN_BIN", "sprite-gen")


def sh(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-1000:]}")


def extract_native(run: Path, cell: int, margin: int, resample: str) -> Path:
    """Re-extract the run into a sibling dir at the game's cell size."""
    work = run.parent / (run.name + f"_{cell}")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(run, work)
    req_p = work / "sprite-request.json"
    req = json.loads(req_p.read_text())
    req["cell"] = {"shape": "square", "width": cell, "height": cell,
                   "safe_margin_x": margin, "safe_margin_y": margin,
                   "size": cell, "safe_margin": margin}
    # foot-centroid keeps the body on the cell axis when the runtime mirrors
    # the cell for left/right; bottom pins every frame to one baseline.
    req["fit"] = {"resample": resample, "align_x": "foot-centroid", "align_y": "bottom"}
    req_p.write_text(json.dumps(req, indent=2))
    shutil.rmtree(work / "frames", ignore_errors=True)
    sh([sprite_gen(), "extract", "--run-dir", str(work)])
    return work


def load(run: Path, direction: str, pose: str) -> list[Image.Image]:
    d = run / "frames" / direction / pose
    fs = sorted(d.glob("frame-*.png"), key=lambda p: int(p.stem.split("-")[1]))
    if not fs:
        sys.exit(f"no extracted frames at {d}")
    return [Image.open(f).convert("RGBA") for f in fs]


def crisp(sheet: Image.Image, colors: int) -> Image.Image:
    """1-bit alpha + a flat palette: no hazy semi-transparent pixels at 32px."""
    a = sheet.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    q = sheet.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT,
                                      dither=Image.NONE).convert("RGBA")
    q.putalpha(a)
    return q


def palette_of(sheet: Image.Image) -> tuple[list[int], dict[tuple, int]]:
    cols = sorted({p[:3] for p in sheet.convert("RGBA").getdata() if p[3] >= 128})
    flat: list[int] = []
    for c in [SENTINEL] + cols:
        flat += list(c)
    flat += [0] * (768 - len(flat))
    return flat, {c: i + 1 for i, c in enumerate(cols)}


def to_paletted(frame: Image.Image, palette: list[int], lookup: dict[tuple, int]) -> Image.Image:
    """Exact colour -> index mapping, so GIF pixels cannot drift from the sheet."""
    p = Image.new("P", frame.size)
    p.putpalette(palette)
    px = frame.load()
    idx = bytearray(frame.width * frame.height)
    for y in range(frame.height):
        row = y * frame.width
        for x in range(frame.width):
            r, g, b, a = px[x, y]
            if a < 128:
                idx[row + x] = 0
                continue
            i = lookup.get((r, g, b))
            if i is None:
                i = min(lookup, key=lambda c: sum((c[j] - (r, g, b)[j]) ** 2 for j in range(3)))
                i = lookup[i]
            idx[row + x] = i
    p.frombytes(bytes(idx))
    return p


def save_gif(frames: list[Image.Image], path: Path, palette: list[int],
             lookup: dict[tuple, int], duration: int) -> None:
    ps = [to_paletted(f, palette, lookup) for f in frames]
    ps[0].save(path, save_all=True, append_images=ps[1:], duration=duration,
               loop=0, disposal=2, transparency=0)


def font(size: int):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def measure(cell_img: Image.Image) -> dict:
    bb = cell_img.getchannel("A").getbbox() or (0, 0, 0, 0)
    op = [p for p in cell_img.getdata() if p[3] >= 128]
    return {"h": bb[3] - bb[1], "w": bb[2] - bb[0], "ink": len(op),
            "colours": len({p[:3] for p in op})}


def gallery(out: Path, name: str, sheet: Image.Image, cell: int,
            reference_dir: Path | None) -> None:
    ref_html = ""
    if reference_dir and reference_dir.is_dir():
        cards = ""
        for p in sorted(reference_dir.glob("*.png"))[:3]:
            im = Image.open(p).convert("RGBA")
            if im.size != (cell * COLS, cell * 4):
                continue
            rp = out / "reference" / (p.stem.replace(" ", "_") + "_8x.png")
            rp.parent.mkdir(parents=True, exist_ok=True)
            im.resize((im.width * UPSCALE, im.height * UPSCALE), Image.NEAREST).save(rp)
            cards += (f'<div class=card><img src="reference/{rp.name}" width=240>'
                      f'<div class=n>{p.stem}</div></div>')
        if cards:
            ref_html = ("<h1 style='margin-top:0'>Reference &mdash; the pipoya wokas in the game</h1>"
                        "<p class=sub>The bar: full 32px height, chunky chibi proportions, "
                        "flat colours, 1px outline.</p>"
                        f"<div class=grid>{cards}</div>")

    rows = "".join(
        f'<div class=card><img src="walk_{d}.gif" width=132><div class=n>{d}</div></div>'
        for d in ORDER)
    idles = "".join(
        f'<div class=card><img src="idle_{d}.png" width=96><div class=n>{d}</div></div>'
        for d in ORDER)
    m = measure(sheet.crop((cell, 0, 2 * cell, cell)))
    html = """<!doctype html><meta charset=utf-8><title>__NAME__ - Woka texture</title><style>
body{background:#16161c;color:#e8e8ef;font:14px/1.5 system-ui,sans-serif;margin:0;padding:30px 34px}
h1{font-size:19px;font-weight:600;margin:34px 0 4px}
p.sub{color:#9a9aa8;margin:0 0 20px}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#9a9aa8;margin:26px 0 12px}
.grid{display:flex;gap:22px;flex-wrap:wrap}
.card{background:#1e1e26;border-radius:10px;padding:12px 14px;text-align:center}
.card img{image-rendering:pixelated;display:block;margin:0 auto}
.card .n{margin-top:7px;color:#cfcfda;font-size:12px}
img.big{image-rendering:pixelated;border-radius:8px}
</style>
__REF__
<h1>__NAME__</h1>
<p class=sub>96x128 RGBA &middot; rows down/left/right/up &middot; 3 frames of 32px
&middot; walk [0,1,2,1] @10fps &middot; idle = static frame 1<br>
down cell: __H__px tall, __W__px wide, __INK__ ink px
(pipoya default: 32 tall, 23-27 wide, ~600 ink)</p>
<img class=big src="__NAME___sheet_8x.png" width="300">
<h2>Walking &mdash; the engine's exact sequence</h2><div class=grid>__ROWS__</div>
<h2>Idle &mdash; the single static frame the engine freezes on</h2><div class=grid>__IDLES__</div>
"""
    html = (html.replace("__REF__", ref_html).replace("__NAME__", name)
            .replace("__H__", str(m["h"])).replace("__W__", str(m["w"]))
            .replace("__INK__", str(m["ink"])).replace("__ROWS__", rows)
            .replace("__IDLES__", idles))
    (out / "preview.html").write_text(html)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, type=Path, help="sprite-gen run dir (directional)")
    ap.add_argument("--out", required=True, type=Path, help="output dir, e.g. characters/<name>/out")
    ap.add_argument("--name", required=True, help="character name (texture file name)")
    ap.add_argument("--cell", type=int, default=32, help="cell size (WorkAdventure: 32)")
    ap.add_argument("--margin", type=int, default=0, help="cell safe margin; 0 fills the cell")
    ap.add_argument("--colors", type=int, default=32, help="palette size (pipoya uses 29-41)")
    ap.add_argument("--resample", default="kcentroid",
                    choices=["kcentroid", "nearest", "lanczos"],
                    help="kcentroid keeps 1px outlines readable at small cells")
    ap.add_argument("--reference-dir", type=Path, default=None,
                    help="optional dir of reference spritesheets for the gallery")
    ap.add_argument("--report-dir", type=Path, default=None,
                    help="where to copy run reports (default: sibling 'report' of --out)")
    ap.add_argument("--no-gallery", action="store_true")
    args = ap.parse_args()

    run = args.run.resolve()
    if not (run / "sprite-request.json").exists():
        sys.exit(f"{run} is not a sprite-gen run (no sprite-request.json)")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    work = extract_native(run, args.cell, args.margin, args.resample)
    print(f"re-extracted at {args.cell}x{args.cell} -> {work}")

    sheet = Image.new("RGBA", (args.cell * COLS, args.cell * len(ROWS)), (0, 0, 0, 0))
    for r, (row_name, direction) in enumerate(ROWS):
        fs = load(work, direction, "walk")[:COLS]
        if direction == "side" and row_name in MIRROR:
            fs = [f.transpose(Image.FLIP_LEFT_RIGHT) for f in fs]
        if len(fs) != COLS:
            sys.exit(f"{direction}/walk: expected {COLS} frames, got {len(fs)}")
        for c, f in enumerate(fs):
            sheet.paste(f, (c * args.cell, r * args.cell))

    csheet = crisp(sheet, args.colors)
    sheet_path = out / f"{args.name}.png"
    csheet.save(sheet_path)
    palette, lookup = palette_of(csheet)

    for i, d in enumerate(ORDER):
        box = lambda c: (c * args.cell, i * args.cell, (c + 1) * args.cell, (i + 1) * args.cell)
        seq = [csheet.crop(box(c)) for c in WALK_SEQ]
        seq = [f.resize((f.width * UPSCALE, f.height * UPSCALE), Image.NEAREST) for f in seq]
        save_gif(seq, out / f"walk_{d}.gif", palette, lookup, 100)
        still = csheet.crop(box(1))
        still.resize((still.width * UPSCALE, still.height * UPSCALE), Image.NEAREST).save(
            out / f"idle_{d}.png")

    big = csheet.resize((csheet.width * UPSCALE, csheet.height * UPSCALE), Image.NEAREST)
    pad, top = 46, 34
    lab = Image.new("RGBA", (big.width + pad, big.height + top), (24, 24, 28, 255))
    lab.paste(big, (pad, top), big)
    dr = ImageDraw.Draw(lab)
    f = font(22)
    for r, d in enumerate(ORDER):
        dr.text((6, top + r * args.cell * UPSCALE + args.cell * UPSCALE // 2 - 12), d,
                fill=(255, 255, 255, 255), font=f)
    for c in range(COLS):
        dr.text((pad + c * args.cell * UPSCALE + args.cell * UPSCALE // 2 - 6, 6), str(c),
                fill=(255, 255, 255, 255), font=f)
    lab.convert("RGB").save(out / f"{args.name}_sheet_8x.png")

    if not args.no_gallery:
        gallery(out, args.name, csheet, args.cell, args.reference_dir)

    report_dir = args.report_dir or (out.parent / "report")
    report_dir.mkdir(parents=True, exist_ok=True)
    for src in [run / "manifest.json", run / "sprite-sheet-alpha.report.json",
                work / "frames" / "frames-manifest.json", work / "sprite-request.json"]:
        if src.exists():
            shutil.copy2(src, report_dir / src.name)

    m = measure(csheet.crop((args.cell, 0, 2 * args.cell, args.cell)))
    soft = sum(1 for v in sheet.getchannel("A").getdata() if 0 < v < 255)
    print(f"{args.name}: {sheet_path} {csheet.size}, {m['h']}px tall / {m['w']}px wide / "
          f"{m['ink']} ink px, palette {len(set(csheet.convert('RGB').getdata()))}, "
          f"{soft} semi-alpha px hardened away")
    print(f"reports -> {report_dir}")


if __name__ == "__main__":
    main()
