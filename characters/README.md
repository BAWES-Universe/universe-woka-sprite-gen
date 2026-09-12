# Characters

One directory per character:

```
<name>/
  spec.json    the generation request (states, directions, cell, frame counts, approval status)
  prompt.txt   the base prompt, so the still can be re-rolled
  base.png     the identity still — the ONE input that must be kept
  out/         generated artifacts: <name>.png, walk_*.gif, idle_*.png, previews
  report/      manifests + extract reports from the run (audit trail)
```

## Approval status

`spec.json` carries an `approval` field:

- `draft` — generated, not signed off. Do not use in game.
- `approved` — a human has looked at it **in game, next to a default woka**.

Nothing in this repo is `approved` yet.

| character | status | height / width / ink (32px cell) | notes |
|-----------|--------|----------------------------------|-------|
| knight01 | draft | 32 / 20 / 382 | pipeline validation sample; detailed armour loses definition at 32px |
| arab_male | draft | 32 / 18 / 427 | size correct; face detail and density still short of the defaults |
| arab_female | draft | 32 / 18 / 400 | as above |

Reference: the game's pipoya wokas measure 32 / 23-27 / ~600. See
`../docs/quality-log.md` for what was rejected and why.

## Adding a character

1. Read `../docs/making-the-base.md`. Get a base you are happy with.
2. Copy an existing `spec.json`, change the description and actions.
3. `./pipeline/character_pipeline.sh characters/<name>`
4. `python3 pipeline/verify_wa.py characters/<name>/out/<name>.png`
5. Look at `out/preview.html`, then upload the texture in game and compare it to
   a default woka at walking distance.
6. Set `"approval": "approved"` only after step 5.
