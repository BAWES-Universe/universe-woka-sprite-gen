#!/usr/bin/env python3
"""Compile indexed, integer-positioned parts directly into engine pixels.

No model, resampling, quantisation, automatic mirroring or animation inference.
The production CLI requires content-bound human base and final approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

from build_wa import ORDER, WALK_SEQ, palette_of, save_gif
from verify_wa import check


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def engine_sha():
    # Bind approvals to all local code that produces or accepts the output.
    root = Path(__file__).parent
    h = hashlib.sha256()
    for name in ('pixel_native.py', 'build_wa.py', 'verify_wa.py', 'evaluate_wa.py'):
        h.update(name.encode())
        h.update((root / name).read_bytes())
    return h.hexdigest()


def load_rig(path):
    rig = read(path)
    require(rig.get('schema') == 'woka-parts/v1', 'unsupported rig schema')
    require(re.fullmatch(r'[a-z0-9_\-]+', rig.get('name', '')), 'invalid character name')
    require(rig.get('provenance', {}).get('license') in ('MIT', 'CC0-1.0', 'owned'),
            'parts need an explicit MIT, CC0-1.0 or owned license; no PIPOYA input')
    require(bool(rig['provenance'].get('author')), 'missing parts author')
    palette = rig.get('palette', {})
    require(1 <= len(palette) <= 32, 'palette must contain 1..32 colours')
    for symbol, color in palette.items():
        require(len(symbol) == 1 and symbol != '.', 'palette symbols must be single characters; . is transparent')
        require(isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color), 'invalid palette colour')
    require(len(set(v.lower() for v in palette.values())) == len(palette), 'duplicate palette colours')
    parts = rig.get('parts', {})
    require(bool(parts), 'missing parts')
    for name, rows in parts.items():
        require(isinstance(rows, list) and 1 <= len(rows) <= 32, f'{name}: invalid rows')
        require(all(isinstance(r, str) for r in rows), f'{name}: rows must be strings')
        require(1 <= len(rows[0]) <= 32 and len({len(r) for r in rows}) == 1, f'{name}: ragged/oversized part')
        require(set(''.join(rows)) <= set(palette) | {'.'}, f'{name}: unknown palette symbol')
        require(set(''.join(rows)) != {'.'}, f'{name}: empty part')
    require(set(rig.get('views', {})) == set(ORDER), 'supply all four independent views')
    for direction, view in rig['views'].items():
        layers = view.get('layers', [])
        require(bool(layers), f'{direction}: no layers')
        require(len({l['id'] for l in layers}) == len(layers), f'{direction}: duplicate layer id')
        for layer in layers:
            require(layer.get('part') in parts, f'{direction}: unknown part')
            require(layer.get('role') in ('head', 'body', 'arm', 'foot', 'accessory'), 'unknown layer role')
            poses = layer.get('poses', [])
            require(len(poses) == 3, 'every layer needs [step A, stand, step B] positions')
            for pos in poses:
                require(isinstance(pos, list) and len(pos) == 2 and all(type(n) is int for n in pos),
                        'positions must be two integers')
                x, y = pos
                rows = parts[layer['part']]
                require(x >= 0 and y >= 0 and x + len(rows[0]) <= 32 and y + len(rows) <= 32,
                        f'{direction}/{layer["id"]}: clipping a part is forbidden')
            if layer['role'] == 'head':
                require(poses[0] == poses[1] == poses[2], 'v1 head registration must be static')
        feet = [l for l in layers if l['role'] == 'foot']
        require(len(feet) == 2, f'{direction}: two separately posed feet required')
        bottoms = [l['poses'][1][1] + len(parts[l['part']]) for l in feet]
        require(bottoms[0] == bottoms[1] == 32, f'{direction}: standing feet must share baseline 32')
        require(any(l['poses'][0] != l['poses'][1] for l in feet) and
                any(l['poses'][2] != l['poses'][1] for l in feet), 'both steps must move a foot')
    return rig


def part_image(rows, palette):
    im = Image.new('RGBA', (len(rows[0]), len(rows)))
    for y, row in enumerate(rows):
        for x, symbol in enumerate(row):
            if symbol != '.':
                c = palette[symbol]
                im.putpixel((x, y), tuple(int(c[i:i+2], 16) for i in (1, 3, 5)) + (255,))
    return im


def cell(rig, direction, column):
    im = Image.new('RGBA', (32, 32))
    for layer in rig['views'][direction]['layers']:
        part = part_image(rig['parts'][layer['part']], rig['palette'])
        im.alpha_composite(part, tuple(layer['poses'][column]))
    return im


def render(rig):
    sheet = Image.new('RGBA', (96, 128))
    for row, direction in enumerate(ORDER):
        frames = [cell(rig, direction, col) for col in range(3)]
        require(len({im.tobytes() for im in frames}) == 3, f'{direction}: collapsed walk poses')
        for col, im in enumerate(frames):
            sheet.paste(im, (32 * col, 32 * row))
    return sheet


def anchors(rig):
    strip = Image.new('RGBA', (128, 32))
    for i, d in enumerate(ORDER):
        strip.paste(cell(rig, d, 1), (32 * i, 0))
    return strip


def binding(base, rig):
    with Image.open(base) as im:
        im.verify()
    return {'base_sha256': sha(base), 'rig_sha256': sha(rig), 'engine_sha256': engine_sha()}


def approve_base(base, rig, reviewer, output):
    require(bool(reviewer.strip()), 'name the human reviewer')
    load_rig(rig)
    receipt = dict(binding(base, rig), schema='woka-approval/v1', stage='base', reviewer=reviewer.strip())
    write(output, receipt)


def check_base(base, rig, approval):
    receipt = read(approval)
    require(receipt.get('schema') == 'woka-approval/v1' and receipt.get('stage') == 'base' and
            bool(receipt.get('reviewer', '').strip()), 'missing human base approval')
    for key, value in binding(base, rig).items():
        require(receipt.get(key) == value, f'stale base approval: {key}; review again')
    return receipt


def save_previews(sheet, out):
    palette, lookup = palette_of(sheet)
    for row, direction in enumerate(ORDER):
        fs = [sheet.crop((c*32, row*32, c*32+32, row*32+32)) for c in range(3)]
        save_gif([fs[c] for c in WALK_SEQ], out / f'walk_{direction}.gif', palette, lookup, 100)
        fs[1].save(out / f'idle_{direction}.png')
    sheet.resize((768, 1024), Image.Resampling.NEAREST).save(out / 'sheet_8x.png')


def build(base, rig_path, approval, out):
    from evaluate_wa import assess
    receipt = check_base(base, rig_path, approval)
    rig = load_rig(rig_path)
    require(not out.exists(), f'{out} exists; choose a fresh build directory')
    out.parent.mkdir(parents=True, exist_ok=True)
    # All validation runs in a sibling temp directory: no partial release output.
    with tempfile.TemporaryDirectory(dir=out.parent, prefix='.woka-') as tmp:
        stage = Path(tmp)
        sheet = render(rig)
        texture = stage / 'texture.png'
        sheet.save(texture)
        save_previews(sheet, stage)
        failures = check(texture)
        report = assess(texture, rig['review'])
        require(not failures and not report['failures'], '; '.join(failures + report['failures']))
        write(stage / 'evaluation.json', report)
        write(stage / 'build.json', dict(binding(base, rig_path), schema='woka-build/v1',
              base_approval_sha256=sha(approval), texture_sha256=sha(texture),
              status='AWAITING_FINAL_HUMAN_APPROVAL', base_reviewer=receipt['reviewer']))
        shutil.copytree(stage, out)
    return out / 'texture.png'


def validate_build(base, rig_path, approval, out):
    from evaluate_wa import assess
    check_base(base, rig_path, approval)
    manifest = read(out / 'build.json')
    require(manifest.get('schema') == 'woka-build/v1', 'invalid build manifest')
    expected = dict(binding(base, rig_path), base_approval_sha256=sha(approval), texture_sha256=sha(out/'texture.png'))
    require(all(manifest.get(k) == v for k, v in expected.items()), 'stale build; rebuild before approval')
    rig = load_rig(rig_path)
    require(Image.open(out/'texture.png').convert('RGBA').tobytes() == render(rig).tobytes(),
            'texture differs from compiled rig')
    require(all((out / f'walk_{d}.gif').exists() and (out / f'idle_{d}.png').exists() for d in ORDER),
            'missing required previews')
    failures = check(out/'texture.png') + assess(out/'texture.png', rig['review'])['failures']
    require(not failures, '; '.join(failures))
    return expected


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('anchors', help='preview standing views before human approval; no walking output')
    p.add_argument('--rig', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    for command in ('approve-base', 'build', 'approve-final', 'release'):
        p = sub.add_parser(command)
        for flag in ('base', 'rig', 'out'):
            p.add_argument('--'+flag, type=Path, required=True)
        if command != 'approve-base':
            p.add_argument('--approval', type=Path, required=True)
        if command.startswith('approve'):
            p.add_argument('--reviewer', required=True)
            p.add_argument('--human-reviewed', action='store_true', required=True)
        if command == 'release':
            p.add_argument('--destination', type=Path, required=True)
    args = ap.parse_args()
    try:
        if args.cmd == 'anchors':
            anchors(load_rig(args.rig)).save(args.out)
        elif args.cmd == 'approve-base':
            approve_base(args.base, args.rig, args.reviewer, args.out)
        elif args.cmd == 'build':
            print(build(args.base, args.rig, args.approval, args.out))
        else:
            bound = validate_build(args.base, args.rig, args.approval, args.out)
            final_path = args.out / 'final-approval.json'
            if args.cmd == 'approve-final':
                require(bool(args.reviewer.strip()), 'name the human reviewer')
                write(final_path, dict(bound, schema='woka-approval/v1', stage='final', reviewer=args.reviewer.strip()))
            else:
                final = read(final_path)
                require(final.get('schema') == 'woka-approval/v1' and final.get('stage') == 'final' and
                        bool(final.get('reviewer', '').strip()) and all(final.get(k) == v for k, v in bound.items()),
                        'missing or stale final human approval')
                require(not args.destination.exists(), 'release destination already exists')
                args.destination.parent.mkdir(parents=True, exist_ok=True)
                with args.destination.open('xb') as dest:
                    dest.write((args.out/'texture.png').read_bytes())
                print(args.destination)
        return 0
    except (Invalid, ValueError, KeyError, TypeError, OSError) as exc:
        print(f'HOLD: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
