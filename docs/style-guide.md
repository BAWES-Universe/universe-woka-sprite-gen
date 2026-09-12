# Style guide — what "good" means at 32 pixels

The game's own sprites are the bar, not the generated preview. Measure, do not
eyeball: `pipeline/compare_wa.py` prints the same numbers for any texture.

## The measured bar

Per `32×32` cell, down-facing row, middle frame:

| sprite | cell height | cell width | ink pixels | colours/sheet |
|--------|------------|-----------|------------|----------------|
| pipoya default wokas (in game) | 32 | 23-27 | ~600 | 29-41 |
| our first attempt (rejected) | 28 | 11-12 | ~240 | 16 |
| our corrected-shape attempt | 32 | 18-20 | ~400-430 | 30-32 |

Read the second column first. **Height is what the player perceives as "my
character is the right size"**; width and ink density are what make it look
finished rather than thin. A sprite can be exactly 32×32 and still look tiny if
the figure inside only occupies 11 pixels of width.

## Acceptance checklist

Format (enforced by `verify_wa.py` in CI):

- [ ] 96×128 RGBA, 4 rows × 3 columns of 32×32.
- [ ] Character height ≥30px in all four rows (we ship 32).
- [ ] 1-bit alpha — zero semi-transparent pixels.
- [ ] ≤32 colours.
- [ ] Walk GIF frames pixel-identical to the shipped texture, in the engine's
      `[0,1,2,1]` order.

Art (needs a human):

- [ ] Same character in all 12 cells — same clothes, colours, proportions.
- [ ] Column 1 of every row reads as a standing pose.
- [ ] Row 1 and row 2 face opposite ways; row 3 shows no face.
- [ ] Feet on a shared baseline; no vertical bob or horizontal drift.
- [ ] Face is readable — eyes, brows, mouth present, not a smooth blob.
- [ ] Materials are distinguishable where they touch (dark outline or value split).
- [ ] At 100% zoom it reads as pixel art, not as a shrunk illustration.

## Known limits of the automated path

Stated plainly so nobody re-litigates it:

- **Faces are the weak point.** At 32px a face is ~10×8 pixels. AI-generated
  bases rarely put the eyes exactly where a 32px face wants them, so faces come
  out mushy. Hand-drawn pipoya faces use 1px eye whites + a dark pupil; that is
  craft, not prompting.
- **Detail density trails hand-drawn work.** Our sprites carry ~430 ink pixels
  against pipoya's ~620. Cloth folds, belts and hair strands do not survive the
  reduction.
- **Automated runs are stochastic.** The same prompt does not give the same
  pixels. That is why the base still and the shipped texture are committed: the
  deterministic half is reproducible, the generative half is recorded.

Closing those gaps is legitimate future work: a stricter base prompt
(`making-the-base.md`), hand curation of individual frames, or a purpose-built
32px pixel-art model. It is not a pipeline bug.

## Why CI enforces this

Two defects already escaped a human review: a texture whose figures left two
thirds of each cell empty (looked tiny in game), and preview GIFs that were not
the shipped pixels. Both are cheap to check mechanically and expensive to find
in game. `verify_wa.py` exists so they cannot come back.
