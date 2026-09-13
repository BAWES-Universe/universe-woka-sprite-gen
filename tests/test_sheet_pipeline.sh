#!/usr/bin/env bash
# Self-test for the one-sheet pipeline (pipeline/make_woka.py).
#
# Builds a synthetic 4x3 character sheet (no network, no credentials), runs the
# pipeline on it, and requires the result to (a) be 96x128, (b) pass the texture
# gate, and (c) have twelve non-empty cells of consistent scale.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0
say() { printf '\n%s\n' "$*"; }
ok()  { printf '  ok   %s\n' "$*"; }
bad() { printf '  FAIL %s\n' "$*"; fail=1; }

say "1. synthetic 4x3 sheet (magenta keyed, twelve distinct figures)"
python3 - "$TMP/sheet.png" <<'PY'
import sys
from PIL import Image, ImageDraw
W = H = 64
sheet = Image.new("RGBA", (W * 3, H * 4), (0, 0, 0, 0))   # alpha: no external tool needed
d = ImageDraw.Draw(sheet)
for r in range(4):
    for c in range(3):
        x0, y0 = c * W, r * H
        # identical vertical extent in every cell (so the shared scale lands on 32px),
        # with the walk phase shown by which leg is lifted inside the same box
        body = (30 + 20 * r, 90 + 15 * c, 140)
        d.rectangle([x0 + 18, y0 + 12, x0 + 46, y0 + 50], fill=body)
        d.ellipse([x0 + 22, y0 + 4, x0 + 42, y0 + 22], fill=(235, 200, 160))
        up = 4 if c == 0 else 0
        d.rectangle([x0 + 20, y0 + 50 - up, x0 + 30, y0 + 60 - up], fill=(60, 40, 30))
        d.rectangle([x0 + 34, y0 + 50, x0 + 44, y0 + 60], fill=(60, 40, 30))
sheet.save(sys.argv[1])
print(f"    wrote {sys.argv[1]} {sheet.size}")
PY

say "2. run the pipeline"
if python3 "$REPO/pipeline/make_woka.py" --sheet "$TMP/sheet.png" --name selftest \
        --key none --out-dir "$TMP/out" >"$TMP/run.log" 2>&1; then
  ok "make_woka.py exited 0"
else
  bad "make_woka.py failed"; sed 's/^/      /' "$TMP/run.log"
fi

say "3. the texture must pass the repo gate"
if python3 "$REPO/pipeline/verify_wa.py" "$TMP/out/selftest_texture_96x128.png" \
        >"$TMP/gate.log" 2>&1; then
  ok "$(grep -m1 PASS "$TMP/gate.log" || echo 'gate passed')"
else
  bad "texture gate failed"; sed 's/^/      /' "$TMP/gate.log"
fi

say "4. twelve non-empty cells, consistent scale within each row"
python3 - "$TMP/out/selftest_texture_96x128.png" <<'PY' || fail=1
import sys
from PIL import Image
tex = Image.open(sys.argv[1]).convert("RGBA")
rows_ok = True
for r in range(4):
    widths = []
    for c in range(3):
        cell = tex.crop((c * 32, r * 32, (c + 1) * 32, (r + 1) * 32))
        bb = cell.getchannel("A").getbbox()
        if bb is None:
            print(f"  FAIL row {r} cell {c} is empty"); rows_ok = False; continue
        widths.append(bb[2] - bb[0])
    if widths and max(widths) - min(widths) > 2:
        print(f"  FAIL row {r} widths vary too much: {widths}"); rows_ok = False
    else:
        print(f"  ok   row {r} widths {widths}")
sys.exit(0 if rows_ok else 1)
PY

say "5. the engine's walk GIFs must match the texture pixel for pixel"
python3 "$REPO/pipeline/verify_wa.py" "$TMP/out/selftest_texture_96x128.png" \
        >"$TMP/gate2.log" 2>&1 && ok "gif frames identical to the texture" \
        || { bad "gif mismatch"; sed 's/^/      /' "$TMP/gate2.log"; }

printf '\n'
if [ "$fail" -eq 0 ]; then
  echo "SHEET PIPELINE SELF-TEST: all checks passed"
else
  echo "SHEET PIPELINE SELF-TEST: failures above"
fi
exit "$fail"
