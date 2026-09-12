#!/usr/bin/env python3
"""Seed real source defects; require the named test to fail with an assertion."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
MUTANTS=[
('eye contrast', 'pipeline/evaluate_wa.py', 'if wy-py < 90 or skin-py < 40:', 'if False:', 'test_eye_white_mutation_rejected'),
('standing column', 'pipeline/evaluate_wa.py', "if heights[1] != [32,32]:", 'if False:', 'test_standing_step_swap_rejected'),
('head jitter', 'pipeline/evaluate_wa.py', 'if len({f.crop(head_box).tobytes() for f in fs}) != 1:', 'if False:', 'test_head_jitter_rejected'),
('approval binding', 'pipeline/pixel_native.py', 'require(receipt.get(key) == value, f\'stale base approval: {key}; review again\')', 'require(True, "removed binding")', 'test_rig_edit_invalidates_base_approval'),
('dimensions', 'pipeline/verify_wa.py', 'ok = False\n            print(f"FAIL {p}")', 'ok = True\n            print(f"FAIL {p}")', 'test_bad_dimensions_fail_cli'),
('outline', 'pipeline/evaluate_wa.py', "if m['dark_boundary_fraction'] < .70:", 'if False:', 'test_dark_outline_mutation_rejected'),
]


def main():
    failed=[]
    for name,path,old,new,test in MUTANTS:
        with tempfile.TemporaryDirectory(prefix='woka-mutant-') as tmp:
            root=Path(tmp)
            for directory in ('pipeline','tests','examples'):
                shutil.copytree(ROOT/directory,root/directory,ignore=shutil.ignore_patterns('__pycache__'))
            p=root/path;source=p.read_text()
            if source.count(old)!=1: raise RuntimeError(f'mutation anchor changed: {name}')
            p.write_text(source.replace(old,new))
            # Compiles first: a syntax failure never counts as a killed defect.
            compile(p.read_text(),str(p),'exec')
            result=subprocess.run([sys.executable,'-W','ignore::DeprecationWarning','-m','unittest',
                                   f'test_pixel_native.NativeTests.{test}'],cwd=root/'tests',capture_output=True,text=True)
            killed=result.returncode!=0 and f'FAIL: {test} ' in result.stderr and 'AssertionError' in result.stderr
            print(f'{"KILLED" if killed else "SURVIVED"} {name}: {test}')
            if not killed: failed.append(name);print(result.stdout+result.stderr)
    return bool(failed)


if __name__=='__main__':sys.exit(main())
