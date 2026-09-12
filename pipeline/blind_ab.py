#!/usr/bin/env python3
"""Local blinded A/B review and conservative, per-character inference.

The reviewer page contains no filenames or hashes. Keep key.json with the
coordinator; do not publish reference pixels or commit generated review pages.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import secrets
import sys

from PIL import Image
from evaluate_wa import measure, wilson_lower


def encoded(image):
    f=io.BytesIO(); image.save(f,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(f.getvalue()).decode()


def prepare(candidate, reference, out):
    a,b=measure(candidate),measure(reference)
    if out.exists(): raise ValueError('choose a fresh A/B directory')
    if a['sha256']==b['sha256']: raise ValueError('candidate and reference are identical')
    order=[candidate,reference]
    if secrets.randbelow(2): order.reverse()
    # Two counterbalanced forms. Respondents should be assigned alternating forms.
    out.mkdir(parents=True)
    study=secrets.token_hex(8)
    key={'schema':'woka-ab/v1','study':study,'candidate_sha256':a['sha256'],
         'reference_sha256':b['sha256'],'forms':{}}
    for form in ('0','1'):
        if form=='1': order.reverse()
        key['forms'][form]={'A':'candidate' if order[0]==candidate else 'reference','B':'candidate' if order[1]==candidate else 'reference'}
        assets=[]
        for path in order:
            im=Image.open(path).convert('RGBA')
            silhouette=Image.new('RGBA',im.size,(30,30,30,255));silhouette.putalpha(im.getchannel('A'))
            assets.append({'sheet':encoded(im),'silhouette':encoded(silhouette)})
        payload=json.dumps({'study':study,'form':form,'assets':assets})
        html='''<!doctype html><meta charset="utf-8"><title>Woka A/B review</title>
<style>body{font:16px system-ui;background:#dedfd9;color:#20232c;max-width:850px;margin:30px auto}
.cards{display:flex;gap:40px}article{padding:20px;background:#bbbfb7;min-width:160px}
.sprite{image-rendering:pixelated;width:32px;height:32px;display:block;margin:18px}
select,input,button{font:inherit;margin:8px;padding:8px}label{display:block}.dark{background:#343848;color:white}
</style><h1>Which character reads better at game size?</h1>
<p>Keep browser zoom at 100%. Inspect both characters on both backgrounds, in all directions.
Choose tie if neither is better. Judge clarity and motion, not your favourite clothing.</p>
<button id="background">Switch background</button><button id="silhouette">Toggle silhouette</button>
<select id="direction"><option value="0">Down</option><option value="1">Left</option><option value="2">Right</option><option value="3">Up</option></select>
<label><input id="walk" type="checkbox" checked> Walking (uncheck for standing)</label>
<div class="cards"><article>A<div class="sprite" id="A"></div></article><article>B<div class="sprite" id="B"></div></article></div>
<label>Anonymous reviewer ID <input id="reviewer" required maxlength="100"></label>
<div id="questions"></div><button id="save">Download ballot</button><p id="notice"></p>
<script>const data=PAYLOAD;let phase=0,silhouette=false;
const seq=[0,1,2,1],criteria=['overall','face','silhouette','identity','motion'];
for(const name of criteria){const label=document.createElement('label');label.textContent=name+' ';const s=document.createElement('select');s.id=name;
for(const v of ['', 'A','B','tie']){const o=document.createElement('option');o.value=v;o.textContent=v||'Choose';s.append(o)}label.append(s);document.getElementById('questions').append(label)}
function draw(){const row=Number(document.getElementById('direction').value),col=document.getElementById('walk').checked?seq[phase]:1;
['A','B'].forEach((n,i)=>{const el=document.getElementById(n);el.style.backgroundImage='url('+data.assets[i][silhouette?'silhouette':'sheet']+')';el.style.backgroundPosition=(-col*32)+'px '+(-row*32)+'px'})}
setInterval(()=>{phase=(phase+1)%4;draw()},100);draw();
document.getElementById('background').onclick=()=>document.querySelectorAll('article').forEach(x=>x.classList.toggle('dark'));
document.getElementById('silhouette').onclick=()=>{silhouette=!silhouette;draw()};
document.getElementById('save').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim(),votes={};
for(const name of criteria)votes[name]=document.getElementById(name).value;
if(!reviewer||Object.values(votes).some(x=>!x)){document.getElementById('notice').textContent='Complete every answer first.';return}
const ballot={schema:'woka-ballot/v1',study:data.study,form:data.form,reviewer,votes};
const url=URL.createObjectURL(new Blob([JSON.stringify(ballot,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ballot.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
</script>'''.replace('PAYLOAD',payload)
        (out/f'blind-{form}.html').write_text(html)
    (out/'key.json').write_text(json.dumps(key,indent=2)+'\n')
    return key


def tally(key, ballots):
    if key.get('schema')!='woka-ab/v1': raise ValueError('invalid study key')
    seen=set(); counts={k:0 for k in ('overall','face','silhouette','identity','motion')};forms={'0':0,'1':0}
    for ballot in ballots:
        if ballot.get('schema')!='woka-ballot/v1' or ballot.get('study')!=key['study']: raise ValueError('wrong study ballot')
        reviewer=ballot.get('reviewer','').strip()
        if not reviewer or reviewer in seen: raise ValueError('missing/duplicate reviewer for this pair')
        seen.add(reviewer)
        form=ballot.get('form')
        if form not in forms: raise ValueError('unknown counterbalance form')
        forms[form]+=1
        votes=ballot['votes']
        if set(votes)!=set(counts): raise ValueError('missing review criteria')
        for criterion,choice in votes.items():
            if choice not in ('A','B','tie'): raise ValueError('invalid ballot choice')
            if choice!='tie' and key['forms'][form][choice]=='candidate': counts[criterion]+=1
    n=len(seen)
    low={k:round(wilson_lower(w,n),6) for k,w in counts.items()}
    # Every tie counts as a non-win. No dropping unfavourable raters or frames.
    balance=all(v>=n*.4 for v in forms.values())
    passes=n>=40 and balance and counts['overall']/n>=.65 and low['overall']>.5 and counts['face']/n>=.65 and low['face']>.5
    # Other criteria are non-regression sentinels, not equivalence tests.
    passes=passes and all(counts[k]/n>=.5 for k in ('silhouette','identity','motion'))
    return {'schema':'woka-ab-result/v1','n':n,'forms':forms,'candidate_wins':counts,'wilson_95_lower':low,
            'verdict':'HUMAN_AB_WIN_FOR_THIS_PAIR' if passes else 'NOT_ESTABLISHED',
            'scope':'single character pair; requires independent raters, mechanical pass and final human approval'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--candidate',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('tally');p.add_argument('--key',type=Path,required=True);p.add_argument('ballots',type=Path,nargs='+');p.add_argument('--out',type=Path)
    a=ap.parse_args()
    try:
        if a.cmd=='prepare': prepare(a.candidate,a.reference,a.out);print(a.out);return 0
        result=tally(json.loads(a.key.read_text()),[json.loads(p.read_text()) for p in a.ballots])
        body=json.dumps(result,indent=2)+'\n'
        if a.out: a.out.write_text(body)
        else: print(body,end='')
        return 0 if result['verdict']=='HUMAN_AB_WIN_FOR_THIS_PAIR' else 1
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f'HOLD: {e}',file=sys.stderr);return 2


if __name__=='__main__': sys.exit(main())
