# How to make a woka, end to end

One character = one run of this sequence. Budget ~6 minutes of generation plus
review time. Everything after generation is deterministic.

## 0. Prerequisites

- `sprite-gen` installed and pinned (see `tools-and-versions.md`).
- Image backend logged in (`codex login`, or a grok credential).
- An approved base image — see `making-the-base.md`. **Do not skip approval.**

## 1. Create the character directory

```
characters/<name>/
  spec.json      the request: states, directions, cell, frame counts
  prompt.txt     the base prompt (used to (re)generate base.png)
  base.png       the approved identity still
  out/           generated artifacts (committed)
  report/        manifests and extract reports (committed)
```

Copy an existing character's `spec.json` as the template. The important parts:

```json
{
  "layout": "taxonomy/v1",
  "directions": { "set": ["down", "side", "up"], "mirror": { "left": "side" }, "anchor_suffix": "idle" },
  "cell": { "width": 256, "height": 256 },
  "states": {
    "down_idle": { "frames": 4, "fps": 4, "loop": true,  "action": "standing idle facing the viewer; this row is the down direction anchor" },
    "down_walk": { "frames": 3, "fps": 10, "loop": true,  "action": "walk cycle: frame one left foot forward, frame two neutral stance feet together, frame three right foot forward" },
    ... same for side_* and up_*
  }
}
```

Why those choices:

- `directions` with `mirror: {left: side}` is the tool's contract default: generate
  `down`, `side` (profile facing camera-right) and `up`, and produce `left` by
  mirroring `side`. Mirroring is pixel-exact and free. Generate a real `left`
  only when the character has a one-sided feature (a bag on one shoulder,
  something held in one hand, hair parted to one side) — otherwise the flip puts
  it on the wrong arm and viewers notice.
- **3 walk frames** because the engine's grid has exactly 3 columns.
- **Walk frame 2 must be a neutral stance** because column 1 is the engine's idle.
- The `<dir>_idle` rows are **anchors**, not game animations. They lock identity
  and facing per direction. They are not the texture's idle (that is column 1).

## 2. Generate

```bash
export SPRITE_GEN_BIN=../sprite-gen/.venv/bin/sprite-gen
./pipeline/character_pipeline.sh characters/<name>
```

The script runs, in order:

1. `prepare` — writes the request, per-state layout guides and prompts.
2. `gen-set --states *_{idle}` — generates the three direction anchors.
3. `extract --states *_{idle}` — **required before stage 4**, see below.
4. `gen-set --states *_{walk}` — generates the walk rows, each using its own
   direction's anchor as the identity reference.
5. `extract` — extracts every row into transparent frames.

`build_wa.py` then re-extracts at true `32×32` and composes the texture and GIFs.

### The two-stage rule (this trips everyone up)

Anchors must be generated **and extracted** before the walk rows can be
generated. `gen-set` refuses otherwise:

    anchor: nothing extracted yet — generate and extract the anchor row '<dir>_idle' first

And a plain `extract` aborts if *any* raw strip is missing (extraction is atomic
by design), so the sequence is always: anchors → `extract --states ...` → walks →
`extract`. `character_pipeline.sh` does this for you; if you drive the CLI by
hand, do the same.

## 3. Build the texture

```bash
python3 pipeline/build_wa.py --run runs/<name> --out characters/<name>/out --name <name>
```

This does the part that makes the output a *game* asset rather than a picture:

1. Re-extracts every frame at `32×32` with the cell's safe margin at **0** so the
   character fills the cell height, the way the game's own sprites do. A 2px
   margin silently shrinks the character to 28px and it looks small in game.
2. Composes the texture: row 0 down, row 1 left (mirrored side), row 2 right,
   row 3 up.
3. Hardens alpha to 1-bit and quantises to ≤32 flat colours, so no hazy
   semi-transparent pixels survive.
4. Writes the walk GIFs **by cropping the finished texture**, so the preview is
   literally the pixels the engine will play — not a separate render.
5. Writes the static idle still per direction from column 1.
6. Writes an 8× preview and a gallery.

## 4. Verify

```bash
python3 pipeline/verify_wa.py characters/<name>/out/<name>.png
```

This is the same gate CI runs. It fails on wrong dimensions, wrong cell count,
a character that does not fill the cell height, soft alpha, an oversized palette,
or GIF frames that do not match the shipped texture pixel for pixel.

## 5. Review like a player, then upload

- Open `characters/<name>/out/preview.html` — all four directions walking.
- Judge the walk as motion. Frame 1 should read as standing.
- Then upload the texture through the game's avatar management and check it
  **in game, next to a default woka**. The 8× preview flatters everything; the
  game is the real test.
- Only then set `"approval": "approved"` in `spec.json`.

## Pitfalls we have already paid for

| pitfall | effect | fix |
|---------|--------|-----|
| safe margin left at 2px during extraction | character 28px tall in a 32px cell → looks tiny in game | extract with margin 0 (`build_wa.py` does) |
| slim realistic base | same, worse: 11px wide, two thirds of the cell empty | chunky chibi base, see `making-the-base.md` |
| white robe + white headdress | merges into one blob at 32px | separate with value or a coloured trim |
| GIF built from a separate render | preview lies about the ship | crop GIFs from the finished texture (as the pipeline does) |
| 16-colour quantise on a shaded sprite | flattens shading | ≤32 colours |
| generating walk rows before extracting anchors | `gen-set` fails | two-stage order above |
| mirroring a one-sided character | held item jumps arms | generate a real `left` row for those |
| expecting an idle animation | the engine shows one static frame | column 1 is the idle pose |
