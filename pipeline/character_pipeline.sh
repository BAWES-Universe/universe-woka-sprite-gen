#!/usr/bin/env bash
# Make one woka, end to end, from characters/<name>/{spec.json,base.png}.
#
#   export SPRITE_GEN_BIN=/path/to/sprite-gen/.venv/bin/sprite-gen
#   ./pipeline/character_pipeline.sh characters/my_character [provider]
#
# Provider defaults to codex. Produces characters/<name>/out/ and /report/.
# Run pipeline/verify_wa.py afterwards — that is the gate.
set -euo pipefail

char_dir="${1:?usage: character_pipeline.sh characters/<name> [provider]}"
provider="${2:-codex}"
root="$(cd "$(dirname "$0")/.." && pwd)"
name="$(basename "$char_dir")"
run="$root/runs/$name"
sg="${SPRITE_GEN_BIN:-sprite-gen}"

spec="$char_dir/spec.json"
base="$char_dir/base.png"
[ -f "$spec" ] || { echo "missing $spec"; exit 1; }
[ -f "$base" ] || { echo "missing $base — the base still is the identity source"; exit 1; }

echo "== $name =="
echo "-- 1/5 prepare"
"$sg" prepare --out-dir "$run" --character-id "$name" \
  --base-image "$base" --request "$spec" \
  --description "$(python3 -c "import json,sys;print(json.load(open('$spec')).get('description',''))")"

# The two-stage rule: anchors must be generated AND extracted before the walk
# rows can be generated, because each walk row bakes its own direction's anchor
# as the identity reference. A plain extract aborts while any raw strip is
# missing, so the anchor extract is scoped with --states.
echo "-- 2/5 direction anchors"
"$sg" gen-set --run-dir "$run" --provider "$provider" \
  --states down_idle,side_idle,up_idle --concurrency 3

echo "-- 3/5 extract anchors (required before stage 4)"
"$sg" extract --run-dir "$run" --states down_idle,side_idle,up_idle

echo "-- 4/5 walk rows (anchored)"
"$sg" gen-set --run-dir "$run" --provider "$provider" \
  --states down_walk,side_walk,up_walk --concurrency 3

echo "-- 5/5 extract all"
"$sg" extract --run-dir "$run"

echo "-- build texture + previews"
python3 "$root/pipeline/build_wa.py" --run "$run" \
  --out "$char_dir/out" --name "$name" \
  ${REFERENCE_DIR:+--reference-dir "$REFERENCE_DIR"}

echo "-- verify"
python3 "$root/pipeline/verify_wa.py" "$char_dir/out/$name.png"

echo "done: $char_dir/out/$name.png"
