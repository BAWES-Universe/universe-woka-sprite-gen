# The one-sheet workflow

One generation produces all twelve frames, and the rest is deterministic. This is
the current recommended path; `docs/how-to-make-a-woka.md` describes the older
per-row route.

## Why one sheet

Generating each row separately gives each row its own reading of the character:
proportions drift between rows, and frames within a row fatten and shrink because
each one gets fitted to the cell on its own. Generating all twelve poses in a
single image keeps them consistent — the model sees every pose in the same pass —
and then a single shared scale can place them without any per-frame fitting.

## The prompt

Ask for a 4-row by 3-column sheet, name what each row is, demand a consistent
scale and ground baseline, and forbid everything that adds artefacts. The working
template is `characters/<name>/prompt.txt`; the essentials:

- "exactly twelve evenly sized cells, arranged in 4 rows and 3 columns"
- the character description, and the approved still passed as `--ref` so identity
  is locked to it
- row 1 front / row 2 left profile / row 3 right profile / row 4 back view
- "the MIDDLE cell must be the neutral standing pose" — the engine's idle is the
  middle column, so that cell is the frame players see standing still
- "EXAGGERATED stride, one foot visibly lifted" — without this the three frames
  read as the same pose
- "consistent character scale and the same ground baseline in every cell"
- "every cell background is flat solid magenta #FF00FF" — the matte needs a key
- "no grid lines, no floor, no drop shadows, no frame numbers, no labels, no text"

Two things that do **not** work, both measured: asking for a pixel grid ("each
pixel a 16px block") — the model ignores it and returns a smooth drawing; and
asking for small figures ("about 100 pixels tall") so the cut to 32px would be
gentler — the model renders at its own scale (~277-333px) regardless. Expect the
figure to arrive around 300px tall, i.e. a ~9:1 reduction to the 32px cell.

## The commands

```bash
# 1. generate the sheet (needs the codex provider logged in; see docs/tools-and-versions.md)
sprite-gen gen --provider codex \
  --ref characters/<name>/base.png \
  --prompt-file characters/<name>/prompt.txt \
  --out characters/<name>/sheet.png

# 2. sheet -> texture + gifs + gallery + report (deterministic, no network)
python3 pipeline/make_woka.py --sheet characters/<name>/sheet.png --name <name>

# 3. the gate
python3 pipeline/verify_wa.py characters/<name>/<name>_texture_96x128.png
```

`make_woka.py` does, in order: background matted with sprite-gen's chroma engine
(`--key magenta`, use `--key none` if the sheet already carries alpha); the sheet
cut into 4x3; each cell cropped to its figure; **one** scale factor computed from
the tallest figure and applied to all twelve; the cells placed into 96x128 with
feet on each cell's baseline; alpha hardened to one bit; the palette quantised
(`--colours`, default 32); the four engine walk GIFs written from the texture with
exact colour->index encoding so no GIF pixel can drift; `report.json` with the
measurements; and `index.html` for review.

## Reviewing

Open `characters/<name>/index.html`. It shows each direction animated at real
size, the idle frame, the measurements, and a download link that carries the true
96x128 file. **Do not save the zoomed preview** — it is enlarged by CSS for
inspection and saving it gives you the wrong resolution.

## What to check before shipping

- the three frames of each row are the same width (see `report.json`) — that is
  what proves nothing is fattening or shrinking
- the middle column reads as standing still
- the walk actually changes pose between frames (exaggerated stride in the prompt)
- the gate passes

## Known limit

Detail. The model renders at ~300px and the cell is 32px, so fine detail is lost
in a ~9:1 reduction; faces read as faces but not with the crispness of the game's
hand-drawn defaults. Prompting does not move this, because the model ignores
requests for a smaller render. Closing it needs a different frame size in the
engine or hand work at 32px — see `docs/quality-log.md`.
