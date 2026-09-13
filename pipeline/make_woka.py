"""One-sheet woka pipeline: a 4x3 character sheet -> a WorkAdventure 96x128 texture.

The sheet is ONE image-generation call containing all twelve frames (4 directions x
3 walk phases). Generating them together is what keeps the character consistent:
the model sees every pose in the same attention pass. Mapping is then deterministic:

  1. optionally matt the background off with sprite-gen's chroma engine
  2. cut the sheet into 4 rows x 3 columns
  3. crop each cell to its figure and scale EVERY cell by ONE shared factor
     (per-frame fitting is what made frames fatten and shrink)
  4. place the twelve cells into a 96x128 texture, feet on each cell's baseline
  5. harden alpha to 1 bit, quantise to a flat palette
  6. write the engine's walk GIFs ([0,1,2,1] @10fps) straight from the texture
  7. write report.json with the measurements, and a gallery HTML for review

Usage:
  python3 pipeline/make_woka.py --sheet characters/<name>/sheet.png --name <name>
                                [--key magenta|none] [--colours 32] [--fps 10]
"""
import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_wa import palette_of, to_paletted          # exact colour -> index GIF encoding

ROWS, COLS = 4, 3
CELL = 32
SEQ = [0, 1, 2, 1]           # the engine's walk order (frame 1 twice)
DIRECTIONS = ["down", "left", "right", "up"]


def bbox(im: Image.Image) -> tuple:
    """Alpha bounding box, falling back to the whole image when fully transparent."""
    return im.getchannel("A").getbbox() or (0, 0, im.width, im.height)


def sprite_gen_bin() -> str:
    """sprite-gen CLI: $SPRITE_GEN_BIN, then PATH, then the usual local install."""
    env = os.environ.get("SPRITE_GEN_BIN")
    if env and Path(env).exists():
        return env
    found = shutil.which("sprite-gen")
    if found:
        return found
    local = Path.home() / "sprite-gen" / ".venv" / "bin" / "sprite-gen"
    return str(local) if local.exists() else "sprite-gen"


def matt(sheet: Path, key: str, work: Path) -> Image.Image:
    """Background removed by sprite-gen's chroma engine (fringe-safe), or as-is."""
    if key == "none":
        return Image.open(sheet).convert("RGBA")
    out = work / (sheet.stem + "_cut.png")
    r = subprocess.run([sprite_gen_bin(), "cutout", str(sheet), "--out", str(out), "--key", key],
                       capture_output=True, text=True)
    if not out.exists():
        print(f"warning: cutout unavailable ({r.returncode}); using the sheet as-is",
              file=sys.stderr)
        return Image.open(sheet).convert("RGBA")
    return Image.open(out).convert("RGBA")


def slice_sheet(sheet: Image.Image):
    """Cut the grid, then each cell to its own figure."""
    cw, ch = sheet.width / COLS, sheet.height / ROWS
    grid = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            box = (int(c * cw), int(r * ch), int((c + 1) * cw), int((r + 1) * ch))
            cell = sheet.crop(box)
            bb = bbox(cell)
            row.append(cell.crop(bb))
        grid.append(row)
    return grid


def compose(grid, colours: int) -> Image.Image:
    """ONE shared scale for all twelve cells, then paste on the cell baselines."""
    tallest = max(f.height for row in grid for f in row)
    scale = CELL / tallest
    tex = Image.new("RGBA", (COLS * CELL, ROWS * CELL), (0, 0, 0, 0))
    for r, row in enumerate(grid):
        for c, fig in enumerate(row):
            w = max(1, round(fig.width * scale))
            h = max(1, round(fig.height * scale))
            s = fig.resize((w, h), Image.Resampling.BOX)
            a = s.getchannel("A").point(lambda v: 255 if v >= 128 else 0)   # 1-bit alpha
            s.putalpha(a)
            cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            cell.paste(s, (max(0, (CELL - w) // 2), CELL - h), s)
            tex.paste(cell, (c * CELL, r * CELL), cell)
    if colours:
        alpha = tex.getchannel("A")
        q = tex.convert("RGB").quantize(colors=colours, method=Image.Quantize.MEDIANCUT,
                                        dither=Image.Dither.NONE).convert("RGBA")
        q.putalpha(alpha)
        tex = q
    return tex


def measures(tex: Image.Image):
    out = {}
    for r, name in enumerate(DIRECTIONS):
        widths, heights, inks = [], [], []
        for c in range(COLS):
            cell = tex.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
            bb = bbox(cell)
            widths.append(bb[2] - bb[0])
            heights.append(bb[3] - bb[1])
            inks.append(sum(1 for p in cell.getdata() if p[3] >= 128))
        out[name] = {"widths": widths, "heights": heights, "ink": inks}
    opaque = [p[:3] for p in tex.getdata() if p[3] >= 128]
    out["colours"] = len(set(opaque))
    out["semi_transparent"] = sum(1 for p in tex.getdata() if 0 < p[3] < 255)
    out["size"] = list(tex.size)
    return out


def _gif(ims, fps, pal=None):
    """GIF frames carrying the texture's exact palette, so pixels cannot drift."""
    ps = [to_paletted(f, pal[0], pal[1]) for f in ims] if pal else ims
    b = io.BytesIO()
    ps[0].save(b, format="GIF", save_all=True, append_images=ps[1:],
               duration=int(1000 / fps), loop=0, disposal=2, transparency=0)
    return b.getvalue()


def write_gifs(tex: Image.Image, out_dir: Path, fps: int, pal=None):
    made = []
    for r, name in enumerate(DIRECTIONS):
        frames = [tex.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)) for c in SEQ]
        p = out_dir / f"walk_{name}.gif"
        p.write_bytes(_gif(frames, fps, pal))
        made.append(p.name)
    return made


def write_gallery(tex: Image.Image, out_dir: Path, name: str, fps: int, m: dict, pal=None):
    """Self-contained review page. The download link carries the real file."""
    b = io.BytesIO()
    tex.save(b, format="PNG")
    png = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
    cards = []
    for r, direction in enumerate(DIRECTIONS):
        idle = tex.crop((CELL, r * CELL, 2 * CELL, (r + 1) * CELL))
        frames = [tex.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)) for c in SEQ]
        idle_uri = "data:image/gif;base64," + base64.b64encode(_gif([idle, idle], 2, pal)).decode()
        walk_uri = "data:image/gif;base64," + base64.b64encode(_gif(frames, fps, pal)).decode()
        d = m[direction]
        cards.append(
            f'<div class=card><div class=hd>{direction}</div><div class=row>'
            f'<img class=big src="{idle_uri}"><img class=big src="{walk_uri}"></div>'
            f'<div class=cap>left: idle (the frame the engine holds) &middot; right: walk '
            f'[0,1,2,1] @{fps}fps<br>widths {d["widths"]} &middot; ink {d["ink"]}</div></div>')
    html = f"""<!doctype html><meta charset=utf-8><title>{name} - woka texture</title><style>
body{{background:#e9e2d4;color:#2f2820;font:15px/1.6 system-ui,sans-serif;margin:0;padding:32px}}
h1{{font-size:23px;margin:0 0 6px}}h2{{font-size:16px;margin:28px 0 12px;color:#5b5145}}
p.sub{{color:#6a6053;max-width:760px;margin:0 0 20px}}
.grid{{display:flex;flex-wrap:wrap;gap:16px}}
.card{{background:#f6f2e9;border:1px solid #d8cfbe;border-radius:12px;padding:14px 16px}}
.hd{{font-weight:700;margin-bottom:10px}}.row{{display:flex;gap:14px}}
.big{{image-rendering:pixelated;width:192px;height:192px;background:#efe9dc;border-radius:8px}}
.cap{{font-size:12px;color:#6a6053;margin-top:8px;max-width:380px}}
.sheet{{margin-top:14px;background:#f6f2e9;border:1px solid #d8cfbe;border-radius:12px;padding:16px}}
</style>
<h1>{name}</h1>
<p class=sub>96x128 texture, 4 rows x 3 columns of 32px cells, up to {m["colours"]} colours,
{m["semi_transparent"]} semi-transparent pixels. Twelve frames from one generation, one shared scale.</p>
<h2>Animation</h2><div class=grid>{''.join(cards)}</div>
<h2>The texture file</h2>
<div class=sheet>
<p style="margin:0 0 10px;font-size:13px;color:#5b5145">Left: exact size (96x128 &mdash; the file the game wants).
Right: 3x zoom, for inspection only &mdash; do not save that one.</p>
<img style="width:96px;height:128px;image-rendering:pixelated" src="{png}">
<img style="width:288px;height:384px;image-rendering:pixelated;margin-left:20px"
     src="data:image/png;base64,{base64.b64encode(_png_bytes(tex.resize((288, 384), Image.Resampling.NEAREST))).decode()}">
<p style="margin:14px 0 0"><a download="{name}_texture_96x128.png" href="{png}"
 style="background:#2f2820;color:#f6f2e9;padding:10px 15px;border-radius:8px;text-decoration:none;font-weight:600">
 Download the 96x128 texture</a></p></div>"""
    (out_dir / "index.html").write_text(html)


def _png_bytes(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--key", default="magenta", choices=["magenta", "white", "green", "none"])
    ap.add_argument("--colours", type=int, default=32)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args()

    out = a.out_dir or Path("characters") / a.name
    out.mkdir(parents=True, exist_ok=True)
    sheet = matt(a.sheet, a.key, out)
    tex = compose(slice_sheet(sheet), a.colours)
    tex.save(out / f"{a.name}_texture_96x128.png")
    pal = palette_of(tex)
    gifs = write_gifs(tex, out, a.fps, pal)
    m = measures(tex)
    (out / "report.json").write_text(json.dumps({"name": a.name, "measures": m,
                                                 "gifs": gifs}, indent=2))
    write_gallery(tex, out, a.name, a.fps, m, pal)
    print(f"{a.name}: {sheet.width}x{sheet.height} sheet -> {tex.size[0]}x{tex.size[1]} texture, "
          f"{m['colours']} colours, {m['semi_transparent']} semi-transparent px")
    for d in DIRECTIONS:
        print(f"   {d:6s} widths {m[d]['widths']}  heights {m[d]['heights']}  ink {m[d]['ink']}")
    print(f"   wrote {out}/index.html, report.json, {len(gifs)} walk gifs")


if __name__ == "__main__":
    main()
