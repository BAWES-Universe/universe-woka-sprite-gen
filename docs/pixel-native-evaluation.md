# Evaluation: mechanically sound is not artistically better

## Three distinct decisions

1. `inspect`: raw, generator-independent measurements. Reports any correctly
   sized reference, including a 40-colour PIPOYA sprite. No candidate-only policy
   is applied to make the incumbent fail unfairly.
2. `gate` / compiler build: candidate meets the preregistered profile. Exit1 on
   measured failures, exit2 on malformed input/missing annotations. A successful
   exit0 is **mechanical PASS**, while JSON keeps quality `NOT_ESTABLISHED` and
   final `HOLD_HUMAN_REVIEW`. Compare's exit0 has exactly the same meaning.
3. `blind_ab.py tally`: candidate can earn `HUMAN_AB_WIN_FOR_THIS_PAIR` under the
   panel protocol. This is evidence to the final human approver, not a shipping
   command and not a universal victory over every PIPOYA character.

Never sort a gallery by opaque pixels and call the top one better. A filled
rectangle has great coverage and terrible character art. A valid-looking face
annotation can still mark the wrong pixels. The final call must include independent
human votes and a human review of annotations and identity continuity.

## Definitions and their limitations

For each of the twelve 32px cells, ink means alpha≥128; coverage=ink/1024;
bounding-box density=ink/(width×height). All semi-alpha is separately rejected.
Masks use 4-connectivity for ink components. Boundary pixels have at least one
transparent/out-of-cell 4-neighbour; dark means encoded Rec.709 luma≤105. We report
both dark-boundary fraction and largest **8-connected** dark boundary component /
all boundary pixels as an outline-continuity proxy. Neither measures the aesthetic
appropriateness of an outline. Hair notches and deliberate breaks need art review.

Palette total variation is half the sum of absolute differences between normalised
opaque RGB histograms in a step and its standing frame. Silhouette IoU compares
opaque masks; centroid-x range measures lateral registration, but arm movement
contributes to it. Declared head ROI must be byte-identical across each row in v1.
This is a static-head style choice, not a claim that all excellent sprites need
zero bob. A future bob profile must compensate declared offsets explicitly.

Each visible face requires native coordinate annotations: ROI, skin sample,
white/pupil pairs, brows and mouth. The gate checks opaque distinct pixels,
adjacency, separation, brightness contrast and anatomical ordering, in all nine
visible-facing frames. Back-facing frames do not need artificial eyes. Face ROI
and head ROI are independent annotations; inspect both. A different legitimate
style (closed eyes, visor, monster, beard hiding mouth) needs another validated
profile. Do not invent white pixels under a helmet just to meet this one.

V1 samples two material ramps per view and enforces presence of three tones with
at least three pixels each per frame. This prevents a single decorative speck from
claiming a shading tone, but does not validate material boundaries or cloth folds.
Identity across directions is partly guaranteed by reused parts and palette, but
hair/outfit correspondence still needs manual review. Mirrored lighting can look
wrong even if every histogram matches.

Motion uses two reviewed bottom-foot ROIs. The standing frame must plant both
feet at baseline 32; step A and B must alternate the lifted foot. Lower silhouettes
and head registration must remain within limits. This rejects neutral/step swaps
and frozen poses, but does not prove weight transfer or pleasant cloth motion.

All profile thresholds are frozen in `pipeline/evaluate_wa.py`, not supplied by a
candidate. A profile is an explicit product constraint, not a learned critic.
Changing it requires review and invalidates new-path base approval via the code
hash. Test methods exercise erased eyes/brows/mouth, jitter, outline removal,
wrong neutral column, palette noise, alpha, missing views and foot motion.

## Actual worked example

Input provenance, all 12 cell measurements and SHA-256 hashes are in
[`worked-example.json`](../examples/pixel-native/worked-example.json). PIPOYA is
`Male 01-1.png`, game git blob `d4c12b28e9b1821c5dbad942c1d951c950ea6707`.
Its PNG SHA-256 is
`359c9cac3e90d706e00dd4f123d43e449c2f2c7871ff3e1ec9d1544cb9ad8e3d`.
The current generated Arab male is read from main at `3c74336`.
The prototype is rendered from the original rig in this PR, without invoking a
model or creating a production approval. These are measured values, not projected
examples. Blank human votes remain blank, never substituted with synthetic votes.

| Down-facing standing frame / sheet | PIPOYA Male01 | Current Arab male | Original native prototype |
|---|---:|---:|---:|
| Height |32|32|32|
| Width |26|18|27|
| Ink |647|427|717|
| Cell coverage |63.18%|41.70%|70.02%|
| Bounding-box density |77.76%|74.13%|82.99%|
| Opaque colours/sheet |40|32|12|
| Dark-boundary fraction |88.35%|32.94%|96.43%|
| Dark-boundary continuity proxy |73.79%|18.82%|50.00%|
| Down-row centroid-x range |0.4257px|0.8352px|0.0661px|
| Step A palette TV from stand |0.0532|0.2134|0.0076|
| Step B palette TV from stand |0.0532|0.1911|0.0062|
| Step A silhouette IoU |0.8801|0.8889|0.9642|
| Step B silhouette IoU |0.8801|0.8955|0.9615|
| Annotated face checks |not annotated here|not annotated here|pass all 9 visible-facing cells|
| Blind human result |reference|not collected|**NOT_ESTABLISHED**|

The prototype's 50% outline-continuity proxy is **below PIPOYA's 73.79%** despite
its darker boundary. This is a concrete remaining art defect to inspect, and a
reason not to claim it is already superior. The profile records this proxy rather
than using it as a universal gate because deliberate hair/garment breaks vary.
The prototype's higher IoU can mean *less expressive motion*, and its higher ink
can mean *boxier shape*. Twelve colours demonstrate palette restraint, not greater
detail than forty. These figures support preservation of explicit pixels; they
cannot justify a superiority claim. Reference face annotations are deliberately
not guessed; a comparable face-landmark study is pending an artist's annotation
of both candidates and references. Use face votes for the paired final decision.

### Reproduce locally

```bash
# Pure compiler invocation is for an UNAPPROVED engineering fixture only.
# Production characters use the approval CLI in the runbook.
mkdir -p local-review
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0,'pipeline')
from pixel_native import load_rig, render, save_previews
out=Path('local-review')
sheet=render(load_rig('examples/pixel-native/desert_guide.rig.json'))
sheet.save(out/'fixture.png')
save_previews(sheet,out)
PY
python3 pipeline/verify_wa.py local-review/fixture.png
python3 pipeline/evaluate_wa.py compare local-review/fixture.png \
  --review examples/pixel-native/review.json \
  --reference '/your/local/game/play/public/resources/characters/pipoya/Male 01-1.png' \
  --out local-review/comparison.json
```

The rig is read by the production compiler. This fixture command does not create
base/final approval receipts, and the release command cannot publish it without
them. Local preview generation is useful for engineering tests, not authorisation.

## Blinded A/B protocol

Before seeing results, freeze candidate and reference hashes, pairing and the
profile. Match identity type/clothing complexity/body category where possible;
include all 12 preselected characters in a portfolio pilot. Choose the references
before generating candidates to avoid selecting a weak incumbent after the fact.

Recruit ≥40 independent target users per pair, excluding creators and owners.
Use anonymous IDs assigned by a coordinator who prevents duplicate humans. For
half the respondents open `blind-0.html`, and for half `blind-1.html`; both are
labelled only A/B and use opaque embedded image data. Keep `key.json` away from
raters. Do not send the original filenames, quality scores, art-method labels or
this report with the task. Tooling cannot prevent a technical participant
recognising PIPOYA by appearance; ask prior familiarity and report that limitation.

Show logical 1:1 scale first, on light/dark backgrounds, four directions standing
and walking at 10fps. Silhouette toggle removes colour cues. The page never
presents an 8× beauty shot as the primary comparison. The research coordinator
should verify browser zoom 100% and direction/animation controls once per setup.
Ask overall, face clarity, silhouette readability, identity consistency and motion
preference, each A/B/tie. A participant checks all four directions before voting;
the page instructs this but does not enforce viewing time.

For a separate diagnostic face task, show each visible face at 1:1 for two seconds,
then ask forced-choice visible eye count (0/1/2), mouth location (above/below eyes),
and facing direction. Proposed acceptance is ≥90% correct for eye-count/facing,
≥80% mouth placement with no decline versus reference. This task requires a
moderator or a future timed test UI; it is not implemented in the current ballot
page, and the current code must not claim its thresholds were met.

```bash
python3 pipeline/blind_ab.py prepare \
  --candidate local-review/fixture.png \
  --reference '/your/local/game/play/public/resources/characters/pipoya/Male 01-1.png' \
  --out local-review/study-01
# Coordinator assigns pages and collects each downloaded ballot exactly once.
python3 pipeline/blind_ab.py tally --key local-review/study-01/key.json \
  local-review/ballots/*.json --out local-review/ab-result.json
```

The per-pair tally requires ≥65% candidate wins on overall and face, with a
Wilson 95% lower bound >50% for both. With 40 raters, 26 wins (65%) alone do not
clear the confidence bound; 28/40 clears it. Ties count in n as non-wins. At least
40% of respondents must use each form. Silhouette/identity/motion need candidate
wins on ≥50% of all ballots as additional product warning thresholds; these are
not formal non-inferiority confidence tests. Report counts and ties as well as
verdicts. No optional stopping: collect the preregistered sample even if the first
few votes look good. Per-pair results cannot be pooled into 480 independent votes
when the same 40 humans rated 12 characters.

## Mutation evidence

`python3 tests/mutate_native.py` makes one source change at a time in temporary
copies and runs its named test. It checks the modified file compiles and requires
that exact test to fail with `AssertionError`; setup exceptions and syntax errors
do not count. Six mutations remove: eye contrast, standing-column check, head
registration, approval hash binding, malformed-dimension failure, dark-outline
check. The normal integration suite additionally mutates output pixels, GIF timing
and order, manifests, approvals and annotations. CI runs both suites without a
model, external data, GPU, API keys or network calls.
