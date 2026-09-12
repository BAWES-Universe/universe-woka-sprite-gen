# Quality log

A blunt record of what was tried, what it measured, and what was rejected. Keep
appending — the point is that nobody has to rediscover this.

## 2026-09-12 · First attempt — grid generation (rejected)

Approach: ask the image model for the whole 3×4 sheet in one pass
(SDXL + IPAdapter, then Flux.2 Klein with a grid template) and cut it up.

Result: 30+ characters crammed into the front row, left and right nearly
identical, grid bleeding everywhere, no usable frames. Conclusion recorded at the
time: **one-shot grid generation is not a viable route**; identity and layout have
to be enforced per row.

## 2026-09-12 · Second attempt — reference conditioning (partial)

Approach: anchor image + reference-latent conditioning across a 12-frame batch,
white-background keying, 32px downscale.

Result: mechanically it produced files; visually the character was inconsistent
and the white keying ate into light-coloured parts. Also: the whole path existed
to work around the fact that the model was being asked for a grid.

## 2026-09-12 · Third attempt — sprite-gen, per-row pipeline (shape correct, quality short)

Approach: [aldegad/sprite-gen](https://github.com/aldegad/sprite-gen) — one image
generation per *state row*, deterministic extraction, then our own adapter to the
WorkAdventure texture format. This fixed the structural failures: one character
per cell, consistent identity across all cells, clean alpha, no grid bleeding.

Measurement of the first three characters, per 32px cell:

| character | height | width | ink px | verdict |
|-----------|--------|-------|--------|---------|
| knight01 | 28 | 20 | 382 | too short (2px safe margin) |
| arab_male | 28 | 11 | 238 | rejected — looked tiny in game |
| arab_female | 28 | 12 | 241 | rejected — looked tiny in game |
| pipoya default (bar) | 32 | 26 | ~647 | reference |

Root cause of "tiny in game": the figures were slim and realistic-proportioned,
so two thirds of every cell was empty, plus a 2px extraction margin capped the
height at 28px.

## 2026-09-12 · Corrected shape pass (size fixed, detail still short)

Changes: base prompts rewritten for chunky chibi proportions in the game's own
style; extraction margin 0; palette 16 → 32.

| character | height | width | ink px |
|-----------|--------|-------|--------|
| knight01 | 32 | 20 | 382 |
| arab_male | 32 | 18 | 427 |
| arab_female | 32 | 18 | 400 |

Size now matches the defaults (32px, all four rows). **Still rejected on quality:
faces are mushy and detail density trails the hand-drawn sprites** (~430 ink px
vs ~620).

## Open quality gaps and the honest reasons

- **Faces.** A 32px face is ~10×8 px. Generated bases rarely place eyes where a
  32px face needs them, so eyes/brows dissolve in the reduction.
- **Detail density.** Cloth folds, belts, hair strands, eye whites do not survive
  the downscale the way hand-drawn sprites do.
- **Automation ceiling.** Hand-driven iteration in ChatGPT has produced visibly
  better bases than the automated prompt path, so the base is a human-gated step
  by design (`making-the-base.md`).

## Next things worth trying (not yet done)

1. Base generated at native 32px logical resolution with hard 16× blocks, so
   drawn detail survives the downscale instead of being averaged away.
2. A stronger face/eye requirement in the base prompt, verified at 8× before any
   row generation.
3. Character designs that read at 32px: fewer materials, high internal contrast,
   strong silhouettes.
4. Hand curation of individual frames after extraction (the generator has a
   curation webview for exactly this).

## Approval status

No character in this repo is approved for the game yet. Every committed
`spec.json` carries `"approval": "draft"` until a human signs off on the texture
in game next to a default woka.
