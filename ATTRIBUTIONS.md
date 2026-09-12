# Attributions

## aldegad/sprite-gen — Apache-2.0

The generation engine (`prepare` / `gen-set` / `extract` / `anchor` / QA) is
[sprite-gen](https://github.com/aldegad/sprite-gen), licensed Apache-2.0.

We **consume it as a pinned dependency** and do not vendor its source:

    version: 2.2.0
    commit:  ed960ac2e8c61b34e34dd47650e4a7a0182cbc0f

Install it separately (see `docs/tools-and-versions.md`). If we ever need to
patch it, fork it and document the patch — do not copy files into this repo.

## Image generation backend

Image generation runs through the operator's own credentials:

- `codex` provider — ChatGPT OAuth login (`codex login`), using its `image_gen`.
- `grok` provider — xAI Imagine, needs `XAI_API_KEY` or a grok login (chroma-only
  transparency; see sprite-gen's `docs/gen.md`).

No credentials are stored in this repository. Generated images are produced
under the operator's own account and are subject to that provider's terms.

## Reference sprites (not included)

The default Woka sprites that ship with the game are PIPOYA free RPG character
sprites, located in the game repo at
`play/public/resources/characters/pipoya/`. They are used **locally only** as a
visual and measurable reference (`pipeline/compare_wa.py`, `docs/style-guide.md`).

They are deliberately **not** copied into this repository. Do not commit them
here.
