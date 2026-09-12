#!/usr/bin/env python3
"""Model-independent pixel measurements. A mechanical pass NEVER means better art.

inspect reports raw measurements; gate needs separately reviewed annotations.
compare evaluates the candidate and records reference metrics without forcing the
reference into our <=32 colour policy. Missing human evidence remains HOLD.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PIL import Image

ORDER = ['down', 'left', 'right', 'up']
NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def luminance(p):
    # Encoded Rec.709 luma proxy (0..255), not WCAG relative luminance.
    return .2126*p[0] + .7152*p[1] + .0722*p[2]


def mask(im):
    return {(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] >= 128}


def components(points, neighbors=NEIGHBORS):
    remaining = set(points)
    sizes = []
    while remaining:
        todo = [remaining.pop()]
        count = 0
        while todo:
            x, y = todo.pop()
            count += 1
            for dx, dy in neighbors:
                q = (x+dx, y+dy)
                if q in remaining:
                    remaining.remove(q)
                    todo.append(q)
        sizes.append(count)
    return sorted(sizes, reverse=True)


def crop(sheet, row, col):
    return sheet.crop((col*32, row*32, col*32+32, row*32+32))


def metric(im):
    points = mask(im)
    bb = im.getchannel('A').getbbox() or (0, 0, 0, 0)
    boundary = [(x, y) for x, y in points if any((x+dx, y+dy) not in points for dx, dy in NEIGHBORS)]
    sizes = components(points)
    dark = {p for p in boundary if luminance(im.getpixel(p)) <= 105}
    return {
        'height': bb[3]-bb[1], 'width': bb[2]-bb[0], 'ink': len(points),
        'coverage': round(len(points)/1024, 4),
        'bbox_density': round(len(points)/max(1, (bb[2]-bb[0])*(bb[3]-bb[1])), 4),
        'components': len(sizes), 'largest_component_fraction': round(max(sizes, default=0)/max(1, len(points)), 4),
        'single_pixel_components': sizes.count(1),
        'dark_boundary_fraction': round(len(dark)/max(1, len(boundary)), 4),
        # Boundary darkness is a proxy, NOT proof of an unbroken artistic outline.
        'dark_boundary_continuity': round(max(components(dark, NEIGHBORS + [(1,1),(1,-1),(-1,1),(-1,-1)]), default=0)/max(1,len(boundary)),4),
        'baseline': bb[3],
        'centroid_x': round(sum(x for x, y in points)/max(1, len(points)), 4),
        'colours': len({im.getpixel(p)[:3] for p in points})}


def measure(path):
    with Image.open(path) as source:
        if source.size != (96, 128):
            raise ValueError('texture must be 96x128')
        im = source.convert('RGBA')
        mode, fmt = source.mode, source.format
    frames = [crop(im, r, c) for r in range(4) for c in range(3)]
    rows = {}
    for r, direction in enumerate(ORDER):
        fs = frames[r*3:r*3+3]
        masks = [mask(f) for f in fs]
        histograms = [Counter(p[:3] for p in f.getdata() if p[3] >= 128) for f in fs]
        palette = set().union(*histograms)
        distance = []
        for i in (0, 2):
            distance.append(round(.5 * sum(abs(histograms[i][p]/max(1,sum(histograms[i].values())) -
                 histograms[1][p]/max(1,sum(histograms[1].values()))) for p in palette), 4))
        rows[direction] = {
            'frames': [metric(f) for f in fs],
            'unique_frames': len({f.tobytes() for f in fs}),
            'mask_iou_to_stand': [round(len(masks[i]&masks[1])/max(1,len(masks[i]|masks[1])),4) for i in (0,2)],
            'palette_total_variation_to_stand': distance,
            'centroid_x_range': round(max(metric(f)['centroid_x'] for f in fs)-min(metric(f)['centroid_x'] for f in fs),4)}
    return {'schema':'woka-metrics/v1', 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'source_mode': mode, 'source_format': fmt,
            'sheet_colours': len({p[:3] for p in im.getdata() if p[3] >= 128}),
            'soft_alpha': sum(0 < p[3] < 255 for p in im.getdata()), 'rows': rows}


def rect(value):
    if not isinstance(value, list) or len(value) != 4 or any(type(n) is not int for n in value):
        raise ValueError('ROI must be four integers')
    x0,y0,x1,y1 = value
    if not 0 <= x0 < x1 <= 32 or not 0 <= y0 < y1 <= 32:
        raise ValueError('ROI outside the cell')
    return tuple(value)


def face_checks(im, annotation, expected_eyes):
    """Test annotated eye/skin contrast and layout, never infer landmarks from colour.

The profile is for visible-eyed humanoids. Masks/helmets need a separately
validated profile, not fake landmarks. Annotation correctness is human-reviewed.
"""
    box = rect(annotation['roi'])
    def point(p):
        if not isinstance(p, list) or len(p) != 2 or any(type(n) is not int for n in p):
            raise ValueError('landmarks must be integer [x,y]')
        x,y = p
        if not box[0] <= x < box[2] or not box[1] <= y < box[3]:
            raise ValueError('landmark outside face ROI')
        pixel = im.getpixel((x,y))
        if pixel[3] != 255:
            raise ValueError('transparent face landmark')
        return luminance(pixel)
    eyes, brows, mouth = annotation['eyes'], annotation['brows'], annotation['mouth']
    if len(eyes) != expected_eyes or len(brows) != expected_eyes:
        raise ValueError('incorrect eye/brow count for direction')
    skin = point(annotation['skin'])
    failures = []
    whites, pupils = [], []
    for eye, brow in zip(eyes,brows):
        white, pupil = eye['white'], eye['pupil']
        whites.append(tuple(white)); pupils.append(tuple(pupil))
        wy, py, by = point(white), point(pupil), point(brow)
        if sum(abs(a-b) for a,b in zip(white,pupil)) != 1:
            failures.append('eye white must touch its pupil')
        if wy-py < 90 or skin-py < 40:
            failures.append('eye contrast: white-pupil >=90 and skin-pupil >=40 required')
        if not 1 <= pupil[1]-brow[1] <= 3 or abs(brow[0]-pupil[0]) > 1 or skin-by < 35:
            failures.append('brow must be dark, above and aligned to eye')
    if len(set(whites+pupils)) != 2*expected_eyes:
        failures.append('eyes must use distinct pixels')
    if expected_eyes == 2 and abs(pupils[0][0]-pupils[1][0]) < 3:
        failures.append('front eyes must be separated by >=3 pixels')
    if not max(p[1] for p in pupils)+2 <= mouth[1] <= box[3]-1 or skin-point(mouth) < 30:
        failures.append('mouth must be below eyes with skin contrast >=30')
    return failures


def assess(path, annotation):
    raw = measure(path)
    failures = []
    if annotation.get('schema') != 'woka-review/v1' or annotation.get('profile') != 'visible-eyes-humanoid/v1':
        raise ValueError('unsupported/missing review profile')
    if set(annotation.get('views', {})) != set(ORDER):
        raise ValueError('review needs all four directions')
    if raw['source_mode'] != 'RGBA' or raw['source_format'] != 'PNG': failures.append('format: PNG RGBA required')
    if raw['sheet_colours'] > 32: failures.append('palette: exceeds 32 colours')
    if raw['soft_alpha']: failures.append('alpha: semi-transparent pixels')
    im = Image.open(path).convert('RGBA')
    for r,direction in enumerate(ORDER):
        row = raw['rows'][direction]
        a = annotation['views'][direction]
        head_box = rect(a['head_roi'])
        if head_box[3]-head_box[1] < 8 or head_box[2]-head_box[0] < 8:
            raise ValueError('head ROI too small to measure registration')
        fs = [crop(im,r,c) for c in range(3)]
        if len({f.crop(head_box).tobytes() for f in fs}) != 1:
            failures.append(f'{direction}: head/face jitter (v1 requires zero changed head pixels)')
        if row['unique_frames'] != 3: failures.append(f'{direction}: duplicated walk poses')
        if row['centroid_x_range'] > 1.25: failures.append(f'{direction}: lateral registration >1.25px')
        if max(row['palette_total_variation_to_stand']) > .12: failures.append(f'{direction}: palette identity drift >0.12 TV')
        if min(row['mask_iou_to_stand']) < .78: failures.append(f'{direction}: silhouette change >22%')
        feet = [rect(b) for b in a['feet_rois']]
        if len(feet) != 2 or any(b[1] < 24 for b in feet): raise ValueError('annotate two feet in lower eight rows')
        def bottom(f,box):
            bb = f.crop(box).getchannel('A').getbbox()
            return bb[3]+box[1] if bb else -1
        heights = [[bottom(f,b) for b in feet] for f in fs]
        if heights[1] != [32,32]: failures.append(f'{direction}: middle frame is not planted standing feet')
        if not ((heights[0][0]-heights[0][1])*(heights[2][0]-heights[2][1]) < 0 and
                max(heights[0]) == max(heights[2]) == 32):
            failures.append(f'{direction}: feet do not alternate a planted/lifted step')
        ramps = a['materials']
        if not isinstance(ramps, dict) or len(ramps) < 2: raise ValueError('annotate at least two material ramps')
        for c,f in enumerate(fs):
            m=row['frames'][c]
            prefix=f'{direction}[{c}]'
            if m['height'] < 30: failures.append(f'{prefix}: height below 30')
            low_width, low_ink = (23,540) if direction in ('down','up') else (18,380)
            if not low_width <= m['width'] <= 28: failures.append(f'{prefix}: width outside {low_width}..28')
            if not low_ink <= m['ink'] <= 760: failures.append(f'{prefix}: ink outside {low_ink}..760')
            if m['dark_boundary_fraction'] < .70: failures.append(f'{prefix}: dark outline coverage below .70')
            if m['largest_component_fraction'] < .995 or m['single_pixel_components']:
                failures.append(f'{prefix}: detached ink/noise')
            if direction != 'up':
                failures.extend(f'{prefix}: {msg}' for msg in face_checks(f,a['face'],2 if direction=='down' else 1))
            hist = Counter('#%02x%02x%02x'%p[:3] for p in f.getdata() if p[3])
            for material, colors in ramps.items():
                if not isinstance(colors,list) or not 3 <= len(colors) <= 4 or len(set(colors)) != len(colors):
                    raise ValueError('materials need 3..4 distinct tones')
                # 3 pixels per tone discourages a single speck being claimed as shading.
                if sum(hist[col.lower()] >= 3 for col in colors) < 3:
                    failures.append(f'{prefix}: {material} lacks three used shading tones (>=3px each)')
    return {'schema':'woka-evaluation/v1','metrics':raw,'failures':failures,
            'mechanical_verdict':'FAIL' if failures else 'PASS',
            'quality_verdict':'NOT_ESTABLISHED', 'final_verdict':'HOLD_HUMAN_REVIEW'}


def wilson_lower(wins, n):
    if not n: return 0.0
    z=1.959963984540054
    p=wins/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/(1+z*z/n)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['inspect','gate','compare'])
    ap.add_argument('texture',type=Path)
    ap.add_argument('--review',type=Path)
    ap.add_argument('--reference',type=Path)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    try:
        if args.command=='inspect':
            result=measure(args.texture)
        else:
            if args.review is None: raise ValueError('--review is required; missing annotations cannot pass')
            result=assess(args.texture,json.loads(args.review.read_text()))
            if args.command=='compare':
                if args.reference is None: raise ValueError('--reference is required')
                result['reference']=measure(args.reference)
        body=json.dumps(result,indent=2,sort_keys=True)+'\n'
        if args.out: args.out.write_text(body)
        else: print(body,end='')
        return 1 if result.get('failures') else 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f'HOLD: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
