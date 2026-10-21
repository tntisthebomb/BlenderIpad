#!/usr/bin/env python3
"""Link the delivered browser application once; validate its portable core there."""
import argparse
import hashlib
import json
import sys
from setup_browser import ROOT, CACHE, run

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def cached_cli_is_valid():
    core=CACHE/'blender-webgpu-build'
    try:
        proof=json.loads((core/'core-validation.json').read_text())
        checks=proof['checks']
        expected={'original_startup_loaded','modeling','modifier','animation','image_io','native_blend_roundtrip'}
        return (checks['version']==[5,2,2] and expected<=checks.keys() and
                all(checks[name] is True for name in expected) and
                proof['scene_test_sha256']==digest(ROOT/'tests/blender_core_scene.py') and
                set(proof['files'])=={'blender.js','blender.wasm'} and
                all(digest(core/'bin'/name)==sha for name,sha in proof['files'].items()))
    except (OSError,ValueError,KeyError,TypeError):return False

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cycles',action='store_true')
    options=parser.parse_args()
    arguments=['--editor']+(['--cycles'] if options.cycles else [])
    if cached_cli_is_valid():
        print('Reusing hash-verified background CLI as the link baseline. All current native link inputs will rebuild; portable core checks run in the NEW delivered browser engine.',flush=True)
        run(sys.executable,ROOT/'scripts/build_blender_core.py',*arguments,'--objects-only')
    else:
        run(sys.executable,ROOT/'scripts/build_blender_core.py',*arguments)
        run(sys.executable,ROOT/'scripts/test_blender_core.py','--webgpu')
    run(sys.executable,ROOT/'scripts/build_blender_core_browser.py','--editor')
