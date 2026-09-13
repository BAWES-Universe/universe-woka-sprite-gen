#!/usr/bin/env bash
# Ask the sprite_strategist subagent (GPT-6 Astra) to investigate this repo.
#
#   tools/ask-astra.sh [output-file] [extra question]
#
# Runs non-interactively under the machine's existing codex login (your ChatGPT
# plan), in a read-only sandbox, so it can read the whole repo and measure things
# without changing anything. Its report is tee'd to the output file.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M)"
OUT="${1:-$HOME/sprite-lab/astra-findings-$STAMP.md}"
EXTRA="${2:-}"
GAME="${GAME_REPO:-$HOME/workadventure/workadventure-universe}"

TASK="Read .codex/agents/sprite-strategist.toml and take its developer_instructions
as your role for this session. Then do that work for this repository.

Specifically:
1. Reproduce the current sprite measurements yourself: run
   python3 pipeline/verify_wa.py characters/*/*_texture_96x128.png and read every
   characters/*/report.json. Report the numbers you actually got.
2. Measure the game's own default wokas for comparison:
   $GAME/play/public/resources/characters/pipoya/
   (their frame size comes from $GAME/play/src/front/Phaser/Entity/PlayerTexturesLoadingManager.ts).
   Compare width, ink coverage, outline continuity and palette size against ours.
3. Say what limits quality. Separate limits that come from the image model (things it
   refuses to do however you prompt it) from limits in our code. Every claim about the
   model must name the exact prompt you would use and how I could falsify it.
4. Give a ranked shortlist of changes, each with: core idea, expected gain against a
   measured number, effort, cost, risk, and what would invalidate it. Include
   approaches that are not \"prompt it better\".
5. Pick one and specify it concretely: exact files, the code or diff, tests, and how
   to verify. Working code, not pseudocode.

Write your answer as a single report. Do not modify any files.

$EXTRA"

cd "$REPO"
echo "agent: sprite_strategist (gpt-6-astra, read-only)  repo: $REPO"
echo "writing report to: $OUT"
echo "-----------------------------------------------------------"
codex exec -m gpt-6-astra --sandbox read-only --skip-git-repo-check "$TASK" 2>&1 | tee "$OUT"
echo "-----------------------------------------------------------"
echo "report saved: $OUT"
