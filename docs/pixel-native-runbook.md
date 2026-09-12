# Run the pixel-native pipeline

Python 3.11 recommended. Everything below runs on an ordinary CPU; no sprite-gen
installation, GPU, API key or login is required for this route.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
bash tests/selftest.sh
python3 tests/mutate_native.py
```

## Author native parts

Start from `examples/pixel-native/desert_guide.rig.json` as a **schema example**.
It is not approved production art. Copy it into `characters/<new-name>/rig.json`,
set name/provenance, then redraw the indexed strings, palette and pose offsets.
`parts` contains rectangular strings at native pixel resolution; `.` is transparent.
`palette` maps each other character to one RGB hex colour. Max 32 colours. Each
view has an ordered `layers` array (back to front), each with id, part, role and
three `[x,y]` positions for step A, stand, step B. Four view definitions are required.

Include the exact original `base.png` the human selected. The base is an identity
reference, not an image that this compiler resizes or converts. The operator/artist
must translate it into the four native views. Do not trace/import PIPOYA pixels.

Inspect and update embedded `review`: the head rectangle, visible face landmarks,
two bottom-foot rectangles and at least two material ramps for each direction.
Coordinates are cell-local; ROIs use Pillow's exclusive right/bottom bounds.
The rig annotations are authoritative for production builds. Export them for
standalone comparison if desired:

```bash
python3 - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('characters/my_character/rig.json').read_text())
Path('characters/my_character/review.json').write_text(json.dumps(r['review'],indent=2)+'\n')
PY
```

## Human gate 1: approve the base and its native translation

```bash
python3 pipeline/pixel_native.py anchors \
  --rig characters/my_character/rig.json --out characters/my_character/anchors.png
```

This is a 128×32 strip in down,left,right,up order, **only standing views**. Inspect
at 1:1 first, then nearest-neighbour zoom. Compare clothing, face and handedness
against the base. Check that the annotations describe real visible features.
Only the human who actually reviewed it runs:

```bash
python3 pipeline/pixel_native.py approve-base \
  --base characters/my_character/base.png --rig characters/my_character/rig.json \
  --reviewer 'Your name' --human-reviewed \
  --out characters/my_character/base.approval.json
```

Do not have an agent assert human review. The CLI records your local declaration;
it does not authenticate a person. Subsequent source/base/rig changes invalidate it.

## Compile and review the actual pixels

```bash
python3 pipeline/pixel_native.py build \
  --base characters/my_character/base.png --rig characters/my_character/rig.json \
  --approval characters/my_character/base.approval.json \
  --out local-builds/my_character-v1
python3 pipeline/verify_wa.py local-builds/my_character-v1/texture.png
```

Use a fresh output directory each time. The build writes only after the checks
pass. Artifacts: `texture.png`, `walk_{direction}.gif` (native 32px),
`idle_{direction}.png` (native 32px), `sheet_8x.png`, `build.json`, `evaluation.json`.
No model call is made and nothing is uploaded. A passing candidate still awaits
final human approval. Keep PIPOYA-containing comparison pages under ignored
`local-review/`. See [the A/B protocol](pixel-native-evaluation.md).

## Human gate 2: approve and copy the release texture

After checking all directions at game size, silhouette and face readability,
identity, material separation, neutral stance and motion:

```bash
python3 pipeline/pixel_native.py approve-final \
  --base characters/my_character/base.png --rig characters/my_character/rig.json \
  --approval characters/my_character/base.approval.json \
  --out local-builds/my_character-v1 --reviewer 'Your name' --human-reviewed
python3 pipeline/pixel_native.py release \
  --base characters/my_character/base.png --rig characters/my_character/rig.json \
  --approval characters/my_character/base.approval.json \
  --out local-builds/my_character-v1 \
  --destination characters/my_character/out/my_character.png
```

This copies one approved PNG to a new path. It does not upload to avatar management.
Never overwrite a previous approved file blindly: give the new release a new
name/path, review the diff, then manage replacements through normal review.
Keep your approval/build receipts with the internal art handoff. The receipts
are not public test fixtures. A/B victory is required before claiming superiority,
while the owner may approve a mechanically valid texture without making that claim.

## PR draft and commit plan

Proposed branch: `codex/pixel-native-woka`, base `3c74336`.

1. `feat(sprite): add pixel-native compiler and reviewed release workflow` — new
   compiler, evaluator, blind review tooling and original example matrices.
2. `test(sprite): reject native quality regressions and stale approvals` — tighten
   existing verification,26 integration tests,6 source mutations, pinned Pillow,
   CI/self-test wiring.
3. `docs(sprite): define native art plan, rights and falsifiable evaluation` —
   design, alternatives/budgets, runbook, evaluation protocol, measured JSON,
   README and attribution updates.

The PR diff contains the complete contents of all changes. No game engine changes,
model training, generation-backend fork, live upload, or final art approvals are
part of it. Follow-up: artist-refined kit and a completed blinded test, then
per-pose cloth/occlusion extensions if the motion pilot justifies them.
