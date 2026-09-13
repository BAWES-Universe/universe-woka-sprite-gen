# AGENTS.md

Guidance for any agent working in this repository.

## What this repo is

A pipeline that turns AI image generation into **WorkAdventure / BAWES Universe woka
textures**. It produces the graphics only; uploading to the game is done by hand
through the in-game avatar management. MIT licensed, built in the open.

## The format contract (do not break it)

One PNG per character, **96x128 RGBA**, a 4x4-free grid of 4 rows x 3 columns of
**32px** cells. Rows are down / left / right / up, row-major, so frame index =
row * 3 + column. Each walk plays frames [0,1,2,1] at 10fps. Column 1 is the standing
pose, and the engine's idle is exactly that one frame — there is no idle animation.
Source of truth is the game fork, not these docs:
`play/src/front/Phaser/Player/Animation.ts` and `PlayerTexturesLoadingManager.ts`.

## Commands

```bash
export SPRITE_GEN_BIN=../sprite-gen/.venv/bin/sprite-gen     # pinned generator

# one sheet per character (recommended; docs/one-sheet-workflow.md)
sprite-gen gen --provider codex --ref characters/<n>/base.png \
  --prompt-file characters/<n>/prompt.txt --out characters/<n>/sheet.png
python3 pipeline/make_woka.py --sheet characters/<n>/sheet.png --name <n>
python3 pipeline/verify_wa.py characters/<n>/<n>_texture_96x128.png

# tests (these are what CI runs)
bash tests/selftest.sh
bash tests/test_sheet_pipeline.sh
```

## Rules

- Never commit assets from `play/public/resources/characters/pipoya/` and never train
  on them. They live in the game repo under their own terms.
- Never commit credentials. Generation needs the machine's own codex login; document
  prerequisites in docs/tools-and-versions.md instead of encoding them.
- Keep CI dependency-light: pillow only, no network, no credentials. Anything that
  needs a model must be mockable, as `tests/selftest.sh` demonstrates with a stub.
- A PR must keep both test scripts and the texture gate green, and must extend them
  for anything new it introduces. A gate that cannot fail is not a gate.
- Report measurements, not impressions. `report.json` and `pipeline/verify_wa.py`
  exist so that claims are checkable.

## Delegation

For sprite-quality strategy, delegate to the specialist subagent defined in
`.codex/agents/sprite-strategist.toml` (runs `gpt-6-astra`, read-only, instructed to
measure first and to separate model limits from ours). Ask for it explicitly:

```
Investigate why our sprites measure below the game's defaults. Delegate the
analysis to the sprite_strategist agent, let it reproduce the numbers itself,
then summarise its ranked shortlist with the measurements it took.
```
