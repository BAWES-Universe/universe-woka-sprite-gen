"""Credential-free integration and negative controls for pixel-native production."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import pixel_native as native
import evaluate_wa as evaluate
import blind_ab
import verify_wa


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rig_path=self.root/'rig.json'
        self.rig_path.write_bytes((ROOT/'examples/pixel-native/desert_guide.rig.json').read_bytes())
        self.rig=native.load_rig(self.rig_path)
        self.base=self.root/'base.png'
        native.anchors(self.rig).save(self.base)
        self.approval=self.root/'base-approval.json'
        self.out=self.root/'build'

    def cli(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'pipeline/pixel_native.py'),*map(str,args)],capture_output=True,text=True)

    def args(self):
        return ['--base',self.base,'--rig',self.rig_path,'--approval',self.approval,'--out',self.out]

    def build(self):
        # Synthetic test approval; never a real user's approval.
        native.approve_base(self.base,self.rig_path,'AUTOMATED TEST FIXTURE',self.approval)
        return native.build(self.base,self.rig_path,self.approval,self.out)

    def texture(self):
        p=self.root/'texture.png';native.render(self.rig).save(p);return p

    def mutate_image(self,action):
        p=self.texture();im=Image.open(p).convert('RGBA');action(im);im.save(p)
        return evaluate.assess(p,self.rig['review'])['failures']

    def test_reproducible_exact_pixels_and_preview_contract(self):
        p=self.build()
        second=self.root/'second'
        native.build(self.base,self.rig_path,self.approval,second)
        self.assertEqual(p.read_bytes(),(second/'texture.png').read_bytes())
        self.assertEqual(native.validate_build(self.base,self.rig_path,self.approval,self.out)['texture_sha256'],native.sha(p))
        self.assertEqual(verify_wa.check(p),[])
        report=evaluate.assess(p,self.rig['review'])
        self.assertEqual(report['failures'],[])
        self.assertEqual(report['quality_verdict'],'NOT_ESTABLISHED')
        im=Image.open(p)
        # Independent hardcoded known pixels at the actual row-major positions.
        self.assertEqual(im.getpixel((32+10,9)),(248,243,219,255))
        self.assertEqual(im.getpixel((32+11,9)),(16,24,35,255))
        self.assertNotEqual(im.crop((32,32,64,64)).tobytes(),im.crop((32,64,64,96)).tobytes())
        self.assertEqual(report['metrics']['rows']['down']['frames'][1]['ink'],717)

    def test_missing_approval_creates_no_output(self):
        result=self.cli('build',*self.args())
        self.assertNotEqual(result.returncode,0)
        self.assertIn('HOLD',result.stderr)
        self.assertFalse(self.out.exists())

    def test_rig_edit_invalidates_base_approval(self):
        native.approve_base(self.base,self.rig_path,'TEST',self.approval)
        self.rig_path.write_text(self.rig_path.read_text()+'\n')
        with self.assertRaisesRegex(native.Invalid,'stale base approval'):
            native.build(self.base,self.rig_path,self.approval,self.out)
        self.assertFalse(self.out.exists())

    def test_base_edit_invalidates_approval(self):
        native.approve_base(self.base,self.rig_path,'TEST',self.approval)
        Image.new('RGBA',(32,32),'red').save(self.base)
        with self.assertRaisesRegex(native.Invalid,'base_sha256'):
            native.build(self.base,self.rig_path,self.approval,self.out)

    def test_engine_edit_invalidates_approval(self):
        native.approve_base(self.base,self.rig_path,'TEST',self.approval)
        a=native.read(self.approval);a['engine_sha256']='0'*64;native.write(self.approval,a)
        with self.assertRaisesRegex(native.Invalid,'engine_sha256'):
            native.build(self.base,self.rig_path,self.approval,self.out)

    def test_release_requires_final_review_and_detects_tamper(self):
        texture=self.build();destination=self.root/'release.png'
        args=['release',*self.args(),'--destination',destination]
        self.assertNotEqual(self.cli(*args).returncode,0)
        self.assertFalse(destination.exists())
        result=self.cli('approve-final',*self.args(),'--reviewer','AUTOMATED TEST FIXTURE','--human-reviewed')
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.cli(*args)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(texture.read_bytes(),destination.read_bytes())
        # A new modified image must never reuse the existing final approval.
        im=Image.open(texture);im.putpixel((45,10),(1,2,3,255));im.save(texture)
        result=self.cli('release',*self.args(),'--destination',self.root/'tampered.png')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('stale build',result.stderr)

    def test_manifest_rehash_cannot_hide_texture_tamper(self):
        texture=self.build();im=Image.open(texture);im.putpixel((45,10),(1,2,3,255));im.save(texture)
        m=native.read(self.out/'build.json');m['texture_sha256']=native.sha(texture);native.write(self.out/'build.json',m)
        with self.assertRaisesRegex(native.Invalid,'differs from compiled rig'):
            native.validate_build(self.base,self.rig_path,self.approval,self.out)

    def test_missing_preview_blocks_final(self):
        self.build();(self.out/'walk_down.gif').unlink()
        with self.assertRaisesRegex(native.Invalid,'missing required previews'):
            native.validate_build(self.base,self.rig_path,self.approval,self.out)

    def test_unknown_symbols_fractional_positions_and_clipping_rejected(self):
        def save(r): native.write(self.rig_path,r);return native.load_rig(self.rig_path)
        r=copy.deepcopy(self.rig);r['parts']['shoe'][0]='?ooooo.'
        with self.assertRaisesRegex(native.Invalid,'unknown palette'): save(r)
        r=copy.deepcopy(self.rig);r['views']['down']['layers'][0]['poses'][0]=[8.5,28]
        with self.assertRaisesRegex(native.Invalid,'two integers'): save(r)
        r=copy.deepcopy(self.rig);r['views']['down']['layers'][0]['poses'][0]=[30,28]
        with self.assertRaisesRegex(native.Invalid,'clipping'): save(r)

    def test_example_annotations_and_recorded_metrics_match_source(self):
        review=json.loads((ROOT/'examples/pixel-native/review.json').read_text())
        self.assertEqual(review,self.rig['review'])
        recorded=json.loads((ROOT/'examples/pixel-native/worked-example.json').read_text())['inputs']['prototype']
        got=evaluate.measure(self.texture())
        # Bytes can vary with PNG encoders; the frozen pixel metrics must not.
        self.assertEqual(recorded['rows'],got['rows'])
        self.assertEqual(recorded['sheet_colours'],got['sheet_colours'])

    def test_all_four_views_required(self):
        del self.rig['views']['left'];native.write(self.rig_path,self.rig)
        with self.assertRaisesRegex(native.Invalid,'four independent'):native.load_rig(self.rig_path)

    def test_unlicensed_parts_rejected(self):
        self.rig['provenance']['license']='PIPOYA';native.write(self.rig_path,self.rig)
        with self.assertRaisesRegex(native.Invalid,'license'):native.load_rig(self.rig_path)

    def test_eye_white_mutation_rejected(self):
        failures=self.mutate_image(lambda im: im.putpixel((42,9),im.getpixel((43,9))))
        self.assertTrue(any('eye contrast' in f for f in failures),failures)

    def test_brow_and_mouth_mutations_rejected(self):
        for x,y,expected in [(11,8,'brow'),(14,12,'mouth')]:
            failures=self.mutate_image(lambda im: im.putpixel((32+x,y),im.getpixel((44,10))))
            self.assertTrue(any(expected in f for f in failures),failures)

    def test_head_jitter_rejected(self):
        def shift(im):
            box=(0,0,32,14);head=im.crop(box);im.paste((0,0,0,0),box);im.paste(head,(1,0))
        self.assertTrue(any('jitter' in f for f in self.mutate_image(shift)))

    def test_standing_step_swap_rejected(self):
        def swap(im):
            a=im.crop((0,0,32,32));b=im.crop((32,0,64,32));im.paste(a,(32,0));im.paste(b,(0,0))
        failures=self.mutate_image(swap)
        self.assertTrue(any('middle frame' in f for f in failures),failures)

    def test_duplicated_walk_rejected(self):
        failures=self.mutate_image(lambda im:im.paste(im.crop((32,0,64,32)),(0,0)))
        self.assertTrue(any('duplicated walk' in f for f in failures),failures)

    def test_palette_noise_and_alpha_rejected(self):
        def noisy(im):
            for x in range(40): im.putpixel((x,20),(x,0,7,128))
        failures=self.mutate_image(noisy)
        self.assertTrue(any('palette:' in f for f in failures));self.assertTrue(any('alpha:' in f for f in failures))

    def test_detached_noise_and_flat_material_rejected(self):
        failures=self.mutate_image(lambda im:im.putpixel((0,0),(0,0,0,255)))
        self.assertTrue(any('detached ink' in f for f in failures))
        def flatten(im):
            for y in range(128):
                for x in range(96):
                    p=im.getpixel((x,y))
                    if p[:3] in ((148,180,181),(199,216,213)): im.putpixel((x,y),(248,243,219,255))
        self.assertTrue(any('shading tones' in f for f in self.mutate_image(flatten)))

    def test_dark_outline_mutation_rejected(self):
        def fade(im):
            for y in range(128):
                for x in range(96):
                    if im.getpixel((x,y))==(38,35,49,255): im.putpixel((x,y),(240,240,240,255))
        self.assertTrue(any('outline' in f for f in self.mutate_image(fade)))

    def test_missing_or_misplaced_annotations_cannot_pass(self):
        review=copy.deepcopy(self.rig['review']);del review['views']['left']
        with self.assertRaisesRegex(ValueError,'all four'):evaluate.assess(self.texture(),review)
        review=copy.deepcopy(self.rig['review']);review['views']['down']['face']['eyes'][0]['white']=[0,0]
        with self.assertRaisesRegex(ValueError,'outside face'):evaluate.assess(self.texture(),review)

    def test_bad_dimensions_fail_cli(self):
        p=self.root/'bad.png';Image.new('RGBA',(95,128)).save(p)
        result=subprocess.run([sys.executable,str(ROOT/'pipeline/verify_wa.py'),str(p)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('FAIL',result.stdout)

    def test_empty_walk_cell_fails_original_gate(self):
        p=self.texture();im=Image.open(p);im.paste((0,0,0,0),(0,0,32,32));im.save(p)
        self.assertTrue(any('column 0' in f for f in verify_wa.check(p)))

    def test_rgb_texture_fails_original_gate(self):
        p=self.texture();Image.open(p).convert('RGB').save(p)
        self.assertTrue(any('mode is' in f for f in verify_wa.check(p)))

    def test_wrong_gif_timing_and_order_fail(self):
        p=self.build();im=Image.open(p)
        fs=[evaluate.crop(im,0,c) for c in (0,2,1,2)]
        palette,lookup=native.palette_of(im)
        native.save_gif(fs,self.out/'walk_down.gif',palette,lookup,200)
        failures=verify_wa.check(p)
        self.assertTrue(any('10fps' in f for f in failures),failures)
        self.assertTrue(any('differs from the texture' in f for f in failures),failures)

    def test_ab_identity_ties_threshold_and_duplicates(self):
        p=self.texture();reference=self.root/'reference.png'
        im=Image.open(p);im.putpixel((45,10),(1,2,3,255));im.save(reference)
        key=blind_ab.prepare(p,reference,self.root/'study')
        page=(self.root/'study/blind-0.html').read_text()
        self.assertNotIn(str(p),page);self.assertNotIn(key['candidate_sha256'],page)
        self.assertEqual(key['forms']['0']['A'],key['forms']['1']['B'])
        def ballots(wins=28):
            result=[]
            for i in range(40):
                form=str(i%2);winner=next(k for k,v in key['forms'][form].items() if v=='candidate')
                result.append({'schema':'woka-ballot/v1','study':key['study'],'form':form,'reviewer':str(i),
                               'votes':{k:winner if i<wins else 'tie' for k in ('overall','face','silhouette','identity','motion')}})
            return result
        self.assertEqual(blind_ab.tally(key,ballots())['verdict'],'HUMAN_AB_WIN_FOR_THIS_PAIR')
        self.assertEqual(blind_ab.tally(key,ballots(26))['verdict'],'NOT_ESTABLISHED')
        self.assertEqual(blind_ab.tally(key,ballots()[:20])['verdict'],'NOT_ESTABLISHED')
        self.assertEqual(blind_ab.tally(key,[])['verdict'],'NOT_ESTABLISHED')
        with self.assertRaisesRegex(ValueError,'duplicate'):blind_ab.tally(key,ballots()+ballots()[:1])
        wrong=ballots();wrong[0]['study']='other'
        with self.assertRaisesRegex(ValueError,'wrong study'):blind_ab.tally(key,wrong)


if __name__=='__main__': unittest.main()
