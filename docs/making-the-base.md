# Making the base image (the quality gate)

Everything downstream inherits this image. A weak base cannot be rescued by any
amount of pipeline tuning — we learned that the hard way (see `quality-log.md`).

**The base must be approved by a human before you generate a single animation
row.** Generation is ~5 minutes per character; a bad base wastes it and, worse,
gets committed as a draft nobody trusts.

Two ways to get a base:

- **A · Manual (recommended for quality).** Generate it yourself in ChatGPT
  (or any image tool you trust), download the still, save it as
  `characters/<name>/base.png`, and continue with the pipeline from step 2.
  In practice hand-driven iterations have produced better faces and detail than
  the automated path.
- **B · Automated.** `sprite-gen gen --provider codex --out .../base.png --prompt-file .../prompt.txt`

Either way, judge the result against the checklist below before proceeding.

---

## The prompt recipe

Two mistakes destroy most bases:

- **Realistic proportions.** A slim 7-head figure leaves two thirds of the
  `32×32` cell empty and looks tiny in game next to the default wokas.
- **Sub-pixel detail.** If the face is drawn as a smooth illustration and then
  downscaled 8×, the eyes become mush. Detail only survives if it is drawn as
  *art pixels*.

So ask for the sprite at its native resolution, upscaled with hard blocks:

> 32×32 pixel art RPG character sprite for a game tile — the sprite itself is
> only 32×32 pixels, shown here scaled up 16× with every art pixel as a hard
> square block, no smoothing, no anti-aliasing.
>
> [CHARACTER: who they are, clothes, colours, held items — keep it to the few
> things that must be recognisable at 32px]
>
> Proportions: big chibi head about 40% of the total height, wide shoulders,
> arms held slightly away from the torso so the outline stays wide and open,
> feet planted apart, the figure fills the whole frame from head to toe.
>
> Face: clearly separate eyes with visible whites and dark pupils, eyebrows,
> nose and mouth; the face is expressive and readable, not blank.
>
> Detail: every part separated by a crisp one-pixel dark outline — headdress
> from face, head from body, arms from torso, robe from legs, boots from floor.
> Use 3-4 flat shading tones per material; no gradients, no texture noise.
>
> Front-facing neutral standing idle, arms relaxed at the sides.
>
> Flat solid magenta (#FF00FF) background, one character centred, no shadow,
> no text, no border, no extra characters.

Two rules that matter more than the rest:

1. **Contrast between adjacent materials.** White robe + white headdress merges
   into one white blob at 32px. Separate them (cream robe vs bright white
   headdress, or a coloured trim/agal).
2. **Chunky, not smooth.** If the result looks like a smooth illustration that
   was shrunk, re-roll it. You want visible blocks.

## Base checklist — do not proceed until every line is yes

- [ ] Exactly one character, centred, nothing else in frame.
- [ ] Flat, uniform background that the extractor can key out (magenta or green
      works; avoid the character's own colours — the extractor auto-selects the
      safest key and will tell you if your subject sits too close to it).
- [ ] Head is large (roughly 40% of the height); body is stocky, not slim.
- [ ] Face has readable eyes, brows and mouth — not a smooth blank face.
- [ ] Adjacent materials are distinguishable from each other, not one flat mass.
- [ ] Visible chunky pixel blocks; no anti-aliasing, no gradients.
- [ ] Feet at the bottom of the frame, head near the top.

## Why this matters, measured

Per 32px cell, against the pipoya wokas that ship in the game:

| base | resulting cell height | width | ink px | verdict |
|------|----------------------|-------|--------|---------|
| slim realistic figure (first attempt) | 28 | 11 | 238 | rejected — looked tiny in game |
| chunky chibi, flat colours | 32 | 18 | 427 | correct size; still short on detail |
| pipoya default (the bar) | 32 | 26 | ~620 | hand-drawn reference |

Sizes, thresholds and the reasoning: `style-guide.md`.
