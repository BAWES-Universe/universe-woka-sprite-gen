#!/usr/bin/env bash
# Self-test for universe-woka-sprite-gen — runs in CI, no generator needed.
#
# A stub stands in for sprite-gen, so the pipeline's real ordering, argument
# wiring, texture composition and the verify gate are all exercised without
# burning image generations. It also asserts the gate REJECTS known-bad textures
# (blank, and a sprite that only fills half its cell) — a gate that cannot fail
# is not a gate.
#
#   bash tests/selftest.sh
set -uo pipefail

fail=0
say() { printf '%s\n' "$*"; }
ok()  { say "  ok   $*"; }
bad() { say "  FAIL $*"; fail=1; }

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d /tmp/hermes-verify-woka.XXXXXX)
trap 'rm -rf "$TMP"' EXIT
CALLS="$TMP/calls.log"
: > "$CALLS"

say "workspace: $TMP"

# ---------------------------------------------------------------- stub generator
cat > "$TMP/stub-sprite-gen" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "${STUB_LOG:?}"
cmd="$1"; shift
run=""; states=""; out=""; request=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run-dir) run="$2"; shift 2;;
    --out-dir) out="$2"; shift 2;;
    --states)  states="$2"; shift 2;;
    --request) request="$2"; shift 2;;
    *) shift;;
  esac
done
case "$cmd" in
  prepare)
    mkdir -p "$out/raw" "$out/frames" "$out/prompts" "$out/references"
    cp "$request" "$out/sprite-request.json";;
  gen-set) : ;;                      # generation is the only thing stubbed out
  extract)
    python3 - "$run" "$states" <<'PY'
import json, os, sys
from PIL import Image, ImageDraw
run, states = sys.argv[1], sys.argv[2]
req = json.load(open(os.path.join(run, "sprite-request.json")))
cw, ch = req["cell"]["width"], req["cell"]["height"]
directions = req.get("directions", {}).get("set", [])
want = [s for s in states.split(",") if s] or list(req["states"])
for s in want:
    d, _, pose = s.partition("_")
    if d not in directions:
        d, pose = "", s
    d_out = os.path.join(run, "frames", d, pose) if d else os.path.join(run, "frames", pose)
    os.makedirs(d_out, exist_ok=True)
    n = int(req["states"][s].get("frames", 3))
    m = 1   # real extracts run with margin 0 and fill the cell; stay under the gate's floor
    for i in range(n):
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        # each frame differs, like a real walk cycle
        w = cw // 4 + (i * 2)
        dr.rectangle([w, m, w + cw // 2, ch - m], fill=(200, 60, 60, 255), outline=(20, 20, 20, 255))
        im.save(os.path.join(d_out, f"frame-{i}.png"))
PY
    ;;
esac
exit 0
STUB
chmod +x "$TMP/stub-sprite-gen"

# ---------------------------------------------------------------- fixture repo + character
cp -r "$REPO" "$TMP/repo"; rm -rf "$TMP/repo/.git"
mkdir -p "$TMP/repo/characters/testbot"
python3 - <<PY
import json
from PIL import Image
spec = {
  "description": "stub-fixture character", "approval": "draft",
  "layout": "taxonomy/v1",
  "directions": {"set": ["down", "side", "up"], "mirror": {"left": "side"}, "anchor_suffix": "idle"},
  "cell": {"width": 256, "height": 256},
  "states": {
    "down_idle": {"frames": 4, "fps": 4, "loop": True, "action": "standing idle front"},
    "down_walk": {"frames": 3, "fps": 10, "loop": True, "action": "walk front"},
    "side_idle": {"frames": 4, "fps": 4, "loop": True, "action": "standing idle side"},
    "side_walk": {"frames": 3, "fps": 10, "loop": True, "action": "walk side"},
    "up_idle":   {"frames": 4, "fps": 4, "loop": True, "action": "standing idle back"},
    "up_walk":   {"frames": 3, "fps": 10, "loop": True, "action": "walk back"},
  },
}
json.dump(spec, open("$TMP/repo/characters/testbot/spec.json", "w"), indent=2)
Image.new("RGBA", (256, 256), (250, 4, 251, 255)).save("$TMP/repo/characters/testbot/base.png")
PY
cp "$TMP/repo/characters/testbot/base.png" "$TMP/base.bak"

# ---------------------------------------------------------------- 1. shellcheck-ish basics
say "1. script hygiene"
bash -n "$TMP/repo/pipeline/character_pipeline.sh" && ok "character_pipeline.sh parses" || bad "character_pipeline.sh syntax"
[ -x "$TMP/repo/pipeline/character_pipeline.sh" ] && ok "executable bit set" || bad "not executable"
grep -q 'set -euo pipefail' "$TMP/repo/pipeline/character_pipeline.sh" && ok "strict mode on" || bad "no strict mode"

say "2. CI workflow parses and points at the gate"
python3 - "$TMP/repo/.github/workflows/verify.yml" <<'PY'
import sys
body = open(sys.argv[1]).read()

# String check always; parse the YAML too when we can, so a reworded or
# restructured workflow is caught rather than silently accepted.
need = ["pull_request", "tests/selftest.sh", "pipeline/verify_wa.py",
        "characters/*/out/*.png"]
missing = [n for n in need if n not in body]
if missing:
    print(f"  FAIL workflow missing {missing}")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("  ok   workflow references both gates (pyyaml absent, string check only)")
    sys.exit(0)

d = yaml.safe_load(body)
runs = [s.get("run", "") for job in d["jobs"].values() for s in job["steps"]]
for want, label in [("selftest.sh", "pipeline self-test"),
                    ("verify_wa.py", "texture gate")]:
    if not any(want in r for r in runs):
        print(f"  FAIL no CI step runs the {label}")
        sys.exit(1)
print(f"  ok   CI runs both gates across {len(d['jobs'])} jobs")
PY
[ $? -eq 0 ] || bad "workflow check"

# ---------------------------------------------------------------- 3. negative: missing base
say "3. negative test: character without a base image"
mv "$TMP/repo/characters/testbot/base.png" "$TMP/repo/characters/testbot/base.hidden"
if STUB_LOG="$CALLS" SPRITE_GEN_BIN="$TMP/stub-sprite-gen" \
   bash "$TMP/repo/pipeline/character_pipeline.sh" characters/testbot codex >"$TMP/neg.log" 2>&1; then
  bad "exited 0 without a base image"
else
  grep -q 'missing' "$TMP/neg.log" && ok "refused with a clear message" || bad "failed but message unclear"
fi
mv "$TMP/repo/characters/testbot/base.hidden" "$TMP/repo/characters/testbot/base.png"

# ---------------------------------------------------------------- 4. full run, stubbed generator
say "4. full pipeline run (stub generator)"
( cd "$TMP/repo" && STUB_LOG="$CALLS" SPRITE_GEN_BIN="$TMP/stub-sprite-gen" \
    bash pipeline/character_pipeline.sh characters/testbot codex ) >"$TMP/run.log" 2>&1
rc=$?
[ $rc -eq 0 ] && ok "pipeline exited 0" || { bad "pipeline exited $rc"; sed -n '1,40p' "$TMP/run.log"; }

say "5. generator call order (the two-stage rule)"
python3 - "$CALLS" <<'PY'
import sys
calls = [l.strip().split() for l in open(sys.argv[1]) if l.strip()]
got = [(c[0], next((a.split("=")[1] for a in c if a.startswith("--states=")), None)) for c in calls]
# our CLI passes --states as two tokens
def states_of(c):
    if "--states" in c:
        return c[c.index("--states") + 1]
    return None
got = [(c[0], states_of(c)) for c in calls]
want = [("prepare", None),
        ("gen-set", "down_idle,side_idle,up_idle"),
        ("extract", "down_idle,side_idle,up_idle"),
        ("gen-set", "down_walk,side_walk,up_walk"),
        ("extract", None),          # extract all rows
        ("extract", None)]         # build_wa re-extracts at the game's 32px
if len(got) != len(want):
    print(f"  FAIL call count {len(got)} != {len(want)}: {got}")
    sys.exit(1)
for i, (g, w) in enumerate(zip(got, want)):
    if g != w:
        print(f"  FAIL call {i + 1}: got {g}, want {w}")
        sys.exit(1)
print("  ok   prepare -> anchors -> extract anchors -> walks -> extract all")
PY
[ $? -eq 0 ] || bad "call order"

say "6. artifacts the pipeline promised"
out="$TMP/repo/characters/testbot/out"
for f in testbot.png walk_down.gif walk_left.gif walk_right.gif walk_up.gif \
         idle_down.png idle_up.png testbot_sheet_8x.png preview.html; do
  [ -s "$out/$f" ] && ok "$f" || bad "$f missing or empty"
done
[ -s "$TMP/repo/characters/testbot/report/sprite-request.json" ] && ok "report copied" || bad "report missing"

say "7. the gate accepts the produced texture"
python3 "$TMP/repo/pipeline/verify_wa.py" "$out/testbot.png" >"$TMP/gate.log" 2>&1
grep -q '^PASS' "$TMP/gate.log" && ok "$(grep '^PASS' "$TMP/gate.log")" || { bad "gate rejected the output"; cat "$TMP/gate.log"; }

say "8. the gate rejects known-bad textures (negative control)"
python3 - "$out/testbot.png" "$TMP" <<'PY'
import sys
from PIL import Image
src, tmp = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
# a) a blank texture: everything transparent
Image.new("RGBA", (96, 128), (0, 0, 0, 0)).save(f"{tmp}/bad_blank.png")
# b) a sprite that only fills the top half of each cell (the "looks tiny in game" bug)
squashed = Image.new("RGBA", (96, 128), (0, 0, 0, 0))
for r in range(4):
    for c in range(3):
        squashed.paste(im.crop((c*32, r*32, c*32+32, r*32+16)), (c*32, r*32))
squashed.save(f"{tmp}/bad_short.png")
PY
for badf in bad_blank bad_short; do
  if python3 "$TMP/repo/pipeline/verify_wa.py" "$TMP/$badf.png" >/dev/null 2>&1; then
    bad "gate passed $badf (should fail)"
  else
    ok "gate rejected $badf"
  fi
done

say "9. the real repo's committed textures still pass"
( cd "$REPO" && python3 pipeline/verify_wa.py characters/*/out/*.png ) >"$TMP/real.log" 2>&1
grep -q 'ALL PASS' "$TMP/real.log" && ok "3 committed textures pass" || { bad "committed textures fail"; tail -5 "$TMP/real.log"; }

say "10. pixel-native compiler, approvals, quality gates and blind review"
(cd "$REPO" && PYTHONWARNINGS=ignore::DeprecationWarning python3 -m unittest discover -s tests -p 'test_pixel_native.py') && ok "pixel-native tests" || bad "pixel-native tests"

say ""
[ $fail -eq 0 ] && say "AD-HOC VERIFICATION: all checks passed" || say "AD-HOC VERIFICATION: failures above"
exit $fail
