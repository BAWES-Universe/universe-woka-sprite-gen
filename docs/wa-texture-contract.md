# The WorkAdventure texture contract

Everything here is taken from our fork of the game, not from documentation or
memory. If the two ever disagree, the code wins — open a PR here and fix this file.

Ground truth files:

    play/src/front/Phaser/Player/Animation.ts                  row/frame mapping, fps, sequences
    play/src/front/Phaser/Entity/PlayerTexturesLoadingManager.ts   32x32 frame size
    play/src/front/Phaser/Entity/Character.ts                  how animations are played

## Geometry

- One texture per character: a single PNG, **96 × 128** pixels, RGBA.
- The engine loads it as a spritesheet with `frameWidth: 32, frameHeight: 32`.
- Frame index is row-major: `index = row * 3 + column`.
- 4 rows × 3 columns = 12 frames.

## Rows and frames

| row | direction | frame indices | walk animation | idle |
|-----|-----------|---------------|----------------|------|
| 0 | `down` (front) | 0, 1, 2 | frames `[0,1,2,1]`, frameRate 10, repeat -1 | frame `[1]` |
| 1 | `left` | 3, 4, 5 | frames `[3,4,5,4]`, frameRate 10, repeat -1 | frame `[4]` |
| 2 | `right` | 6, 7, 8 | frames `[6,7,8,7]`, frameRate 10, repeat -1 | frame `[7]` |
| 3 | `up` (back) | 9, 10, 11 | frames `[9,10,11,10]`, frameRate 10, repeat -1 | frame `[10]` |

Consequences you must design around:

1. **Column 1 of every row is the standing pose.** The walk animation visits
   frame 1 twice, and the idle animation is *only* frame 1. So the middle frame
   must read as a neutral stance with the feet together — frame 0 and frame 2
   are the two steps.
2. **There is no breathing, blinking or idle animation.** `Idle` is
   `frames: [1], repeat: 1`. If a character ever needs an idle animation, that is
   an engine change in `Animation.ts`, not an asset feature.
3. **Left and right are separate rows.** Whether you generate both or mirror one
   is a production choice (see `how-to-make-a-woka.md`), but both rows must exist
   in the file.

## What the engine does not care about

- Colour count, dithering, or palette — as long as the PNG is RGBA.
- Whether alpha is hard or soft (but soft alpha renders as visibly hazy pixels
  at 32px, so we harden it to 1-bit in `pipeline/build_wa.py`).

## What breaks in game

| symptom | cause |
|---------|-------|
| character looks tiny next to default wokas | the figure does not fill its cell — common with slim, realistically-proportioned art |
| character floats or sinks | no shared feet baseline across frames |
| walk looks jittery / wobbles | per-frame scale or horizontal pivot drift between frames |
| mid-stride freeze when standing still | column 1 is not a standing pose |
| sees the wrong direction | rows mapped to the wrong directions |

Tolerances and the exact checks are enforced by `pipeline/verify_wa.py`; the
reasoning and thresholds are in `style-guide.md`.
