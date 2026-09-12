# Rights boundary for native sprites

Reviewed 2026-09-13. This is an engineering permission policy based on the sources
below, not a conclusion about every jurisdiction's copyright exceptions.

## PIPOYA: use is not ownership

The specific [32×32 pack page](https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32)
permits commercial/personal use and editing, but prohibits redistributing or
reselling the assets. The [general site terms](https://pipoya.net/sozai/terms-of-use/)
allow conditional free redistribution for free assets, distinguish independently
created compatible art from modifications, and defer to asset-specific terms.
The two sources therefore do not establish an unrestricted redistribution grant
for the exact files in Universe. The MIT license on the surrounding game code
does not relicense these assets. Paid/supporter assets have separate conditions.

For this PR: use a local copy for measurements and private visual review; commit
only numeric metrics, hashes, provenance URLs and original source parts. Do not
commit a reference PNG, atlas crop, comparison image, embedded A/B HTML, or a
reference-derived parts library. Generated A/B pages contain the actual reference
pixels: keep them local and obtain appropriate permission before public sharing.
Existing distribution in the game is not newly audited/authorised by this PR;
retain the acquired pack's terms and any specific author permission in your
rights records. Do not change its attribution or repackage its source assets.

## Training, fine-tuning and distillation

Neither cited page establishes an explicit grant for our proposed training,
checkpoint redistribution and generated sprite catalogue. Absence of the word
AI does not itself mean training is prohibited, and it also does not settle
whether training/output redistribution is permitted. Therefore the operational
answer is **not approved for this project on the evidence available**. No PIPOYA
training, fine-tuning, reference distillation or image-to-image reconstruction is
part of this implementation. Synthetic outputs derived from restricted sprites
are not a shortcut around the unresolved rights.

To reconsider, obtain written permission from the asset author specifying exact
packs/files, training/fine-tuning/distillation, permitted providers and uploads,
commercial outputs, editable part distribution, checkpoints, attribution and
memorisation/near-copy restrictions. Counsel can assess applicable exceptions if
that is a route BAWES wants; do not silently treat an exception as established.

Fallback: commission original parts with rights to edit, commercially use and
redistribute the source/outputs and, only if required later, train/distribute a
model. Alternatively use provenance-verified CC0 or an express dataset/model
license covering those acts. Keep identity-based train/test splits and a
nearest-neighbour audit; neither substitutes for permission.

## This implementation

`examples/pixel-native/desert_guide.rig.json` is an original program-authored
source-matrix engineering example under this repository's MIT license. It does
not incorporate PIPOYA pixels or model training. A structural license field is a
required operator declaration, **not a legal proof or provenance detector**.
The compiler currently accepts `MIT`, `CC0-1.0`, or `owned`; an artist using
`owned` must have the actual rights agreement on file. Do not convert a third
party asset into `owned` by changing a JSON field.

The optional legacy dependency remains the pinned Apache-2.0 sprite-gen. It is
consumed separately, not vendored, copied or forked. The new module requires only
Pillow. Any concept-generation provider has its own account/output/upload terms;
this PR neither purchases a plan nor grants permission to upload third-party art.
