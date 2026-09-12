# Tools, versions and prerequisites

## Pinned generator

The generation engine is not vendored here. Pin it:

```bash
git clone https://github.com/aldegad/sprite-gen
cd sprite-gen
git checkout ed960ac2e8c61b34e34dd47650e4a7a0182cbc0f   # v2.2.0
python3 -m venv .venv
./.venv/bin/pip install -e .
```

Then point the pipeline at it:

```bash
export SPRITE_GEN_BIN=/absolute/path/to/sprite-gen/.venv/bin/sprite-gen
```

`pipeline/character_pipeline.sh` and `pipeline/build_wa.py` both read
`SPRITE_GEN_BIN`; it defaults to `sprite-gen` on `PATH`.

## Image backend (pick one)

| provider | requires | transparency | notes |
|----------|----------|--------------|-------|
| `codex` (default) | `codex login` — ChatGPT OAuth | native alpha | the path used so far |
| `grok` | `XAI_API_KEY` or a grok login | chroma only (returns JPEG) | built-in fallback provider |

Check what the tool sees:

```bash
$SPRITE_GEN_BIN workflow --kind sprite     # prints provider login/access status as JSON
```

No credentials belong in this repo. Each operator logs in on their own machine.

## Python dependencies

Only `Pillow` for the pipeline scripts:

```bash
pip install pillow
```

`sprite-gen` brings its own dependencies into its own venv; do not install it
into the same environment as these scripts.

## Reference sprites for comparison

`pipeline/compare_wa.py` can compare a texture against a reference spritesheet
if you point it at one. We compare against the pipoya wokas that ship in the
game repo:

```bash
python3 pipeline/compare_wa.py --reference-dir /path/to/workadventure-universe/play/public/resources/characters/pipoya
```

Those files are **not** committed here (see `ATTRIBUTIONS.md`). Without
`--reference-dir` the comparison simply reports our numbers alone.

## CI

`.github/workflows/verify.yml` runs `pipeline/verify_wa.py` over every committed
texture on push and on pull requests. It needs nothing but Python and Pillow —
no generator, no credentials, no network.

## Bumping the pin

When upstream releases a version we want:

1. Check out the new commit in your local `sprite-gen`.
2. Re-run one existing character end to end and diff the output
   (`pixel comparison of the old and new textures`, plus `verify_wa.py`).
3. Update the commit SHA in this file, in `ATTRIBUTIONS.md`, and in the
   `sprite-gen` install snippet in the README.
4. Do it in one commit so the version history stays readable.

Do not track upstream's `main` — a moving dependency makes "why did this
character change?" unanswerable.
