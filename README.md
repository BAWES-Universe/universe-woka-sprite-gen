# universe-woka-sprite-gen

Generate **Woka character textures** (and companions) for BAWES Universe in the
exact format the game engine loads: a `96×128` RGBA spritesheet, 4 rows × 3
columns of `32×32` frames.

**Scope: graphics only.** This repo starts at "a character description" and ends
at "a texture file a human has approved". It does **not** publish, upload or
wire characters into the game — that is a manual step in the game's avatar
management (see [How it reaches the game](#how-it-reaches-the-game)).

---

## The format, in one table

Taken from our fork, not guessed — `play/src/front/Phaser/Player/Animation.ts`:

| row | direction | frame indices | walk sequence | engine idle frame |
|-----|-----------|---------------|---------------|-------------------|
| 0   | down      | 0, 1, 2       | `[0,1,2,1]` @10fps | 1 |
| 1   | left      | 3, 4, 5       | `[3,4,5,4]` @10fps | 4 |
| 2   | right     | 6, 7, 8       | `[6,7,8,7]` @10fps | 7 |
| 3   | up        | 9, 10, 11     | `[9,10,11,10]` @10fps | 10 |

Frames are `32×32` (`PlayerTexturesLoadingManager.ts`: `frameWidth: 32, frameHeight: 32`).
Full detail and the tolerances we enforce: [docs/wa-texture-contract.md](docs/wa-texture-contract.md).

**There is no idle animation in the engine.** `Idle` plays a single static frame
(the middle walk frame of that row). Do not generate breathing loops for the game.

---

## Pixel-native prototype: preserve deliberate 32px art

The alternative compiler now accepts **original indexed parts at 32px** and
composes the twelve frames deterministically. It preserves actual eye pixels,
material tones and head registration. No GPU, model or sprite-gen dependency is
needed for this route. A human still approves the base and final texture.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
bash tests/selftest.sh
python3 pipeline/pixel_native.py anchors \
  --rig examples/pixel-native/desert_guide.rig.json --out /tmp/woka-anchors.png
```

The example is **unapproved engineering art**, not proof that we beat PIPOYA.
The measured front frame is 32px high, 27px wide and 717 ink pixels; quality stays
`NOT_ESTABLISHED` until blind human review. See:

- [Design, five approaches, budgets and two-day/two-week plans](docs/pixel-native-design.md)
- [Production runbook and two human approval gates](docs/pixel-native-runbook.md)
- [Metrics, worked comparison and blind A/B protocol](docs/pixel-native-evaluation.md)
- [PIPOYA licensing and training boundary](docs/pixel-native-licensing.md)

## Legacy generation quickstart

```bash
git clone https://github.com/BAWES-Universe/universe-woka-sprite-gen
cd universe-woka-sprite-gen

# 1. get the generator (pinned — see docs/tools-and-versions.md)
git clone https://github.com/aldegad/sprite-gen ../sprite-gen
cd ../sprite-gen && git checkout ed960ac2e8c61b34e34dd47650e4a7a0182cbc0f
python3 -m venv .venv && ./.venv/bin/pip install -e .
codex login                     # the image backend; see docs/tools-and-versions.md

# 2. make a base still, get it approved (this is the quality gate — see docs/making-the-base.md)
# 3. run the pipeline
cd ../universe-woka-sprite-gen
export SPRITE_GEN_BIN=../sprite-gen/.venv/bin/sprite-gen
./pipeline/character_pipeline.sh characters/my_character
```

Output lands in `characters/<name>/out/`:
`<name>.png` (the shippable texture), `walk_{down,left,right,up}.gif`,
`idle_{down,left,right,up}.png`, `<name>_sheet_8x.png`, `preview.html`.

Verify before you push:

```bash
bash tests/selftest.sh                       # pipeline self-test, no credentials needed
python3 pipeline/verify_wa.py characters/*/out/*.png
```

---

## Repo layout

```
pipeline/
  character_pipeline.sh   one command per character: prepare -> anchors -> rows -> extract
  build_wa.py             run dir -> WA texture + walk GIFs + idle stills + gallery
  verify_wa.py            the gate: format, cell usage, alpha, palette, GIF==sheet
  compare_wa.py           side-by-side against a reference spritesheet
docs/
  wa-texture-contract.md  the engine format, with file-level ground truth
  making-the-base.md      how to make a base image that survives 32px  <- READ THIS FIRST
  how-to-make-a-woka.md   the full runbook, including the anchor two-stage requirement
  style-guide.md          the measured quality bar and the acceptance checklist
  tools-and-versions.md   pinned tool versions, prerequisites, how to bump the pin
characters/
  <name>/                 spec.json, prompt.txt, base.png, out/, report/
tests/selftest.sh         pipeline self-test (stub generator, no credentials needed)
.github/workflows/verify.yml
```

---

## Quality bar (read before generating anything)

Quality is **not** "it produced a file". A character ships when a human approves
the base still and the final texture, and the texture fills its cells like the
game's own sprites do. Measured reference — the pipoya wokas that ship in the
game, per 32px cell:

| sprite | height | width | ink px |
|--------|--------|-------|--------|
| pipoya default (the bar) | 32 | 23-27 | ~600 |
| an early attempt of ours (rejected: looks tiny in game) | 28 | 11 | 238 |
| an accepted-shape attempt | 32 | 18 | 427 |

A slim, realistic-proportioned figure **looks tiny in game** even at the correct
resolution, because two thirds of the cell is empty. Generate chunky chibi
proportions. Details, thresholds and the checklist: [docs/style-guide.md](docs/style-guide.md).

---

## How it reaches the game

Out of scope for this repo, but this is the process:

1. `pipeline/verify_wa.py` passes on the texture.
2. A human approves the texture visually (in-game scale matters more than the 8× preview).
3. The texture is uploaded through the game's **avatar management** as a Woka
   texture, exactly like any other custom spritesheet.
4. In game: pick it, walk all four directions, confirm size next to a default woka.

Publishing at scale (CDN, per-creator catalog, automated sync) is deliberately
not here. If that becomes worth doing, it belongs in its own repo.

---

## Status of the committed characters

The three sample characters under `characters/` (`knight01`, `arab_male`,
`arab_female`) exist to prove the pipeline and the verification gate end to end.
They are marked `draft` in their `spec.json` and **none of them has been approved
for the game** — see [docs/quality-log.md](docs/quality-log.md) for what was
measured and rejected.

## Credits

Pipeline built on [aldegad/sprite-gen](https://github.com/aldegad/sprite-gen)
(Apache-2.0, consumed as a pinned dependency — not vendored). See
[ATTRIBUTIONS.md](ATTRIBUTIONS.md).
