#!/usr/bin/env python3
"""Correct only package metadata after the unchanged UI passed acceptance.

The first validator recorded the manifest just before marking it accepted.
Recognize that exact transition; reject every other unexpected asset change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FRONTEND='6a62b3acfa3ae2e4aee79028e522b0eb81c06e66'
ENGINE='893f6163652f5cde223f9781a61ef4931f4b3444'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--patch-output',type=Path,required=True)
    args=parser.parse_args()
    source=args.input_dir
    manifest=json.loads((source/'delivery-manifest.json').read_text())
    proof=json.loads((source/'editor-validation.json').read_text())
    if manifest['frontendSource']!=FRONTEND or manifest['nativeEngineSource']!=ENGINE:
        raise SystemExit('Expected the exact accepted startup-panel candidate.')
    if manifest['validation']!='automated-frontend-checks-passed' or manifest['physicalSafariAccepted'] is not False:
        raise SystemExit('Expected completed automated checks and pending physical acceptance.')
    for name,expected in proof['assets'].items():
        if Path(name).name!=name:raise SystemExit('Unsafe asset name.')
        if name=='delivery-manifest.json':
            pending={**manifest,'validation':'pending'}
            original=hashlib.sha256((json.dumps(pending,indent=2)+'\n').encode()).hexdigest()
            if expected!=original:raise SystemExit('Unexpected manifest mutation.')
        elif digest(source/name)!=expected:raise SystemExit('Tested runtime asset changed: '+name)
    from validate_startup_diagnostic import TESTS
    if proof['checks']!=list(TESTS):raise SystemExit('Required acceptance checks are missing.')
    for name in TESTS:
        if digest(ROOT/name)!=proof['tests'][name]:raise SystemExit('A tested fixture changed: '+name)
    for name,expected in manifest['nativeEngineAssets'].items():
        if digest(source/name)!=expected:raise SystemExit('Native engine changed: '+name)
    for target,native in [('index.html','blender_editor.html'),('editor.html','blender_editor.html'),
                          ('startup_stats.js','startup_stats.js'),('ipad-startup.html','ipad-startup.html')]:
        if (source/target).read_bytes()!=(ROOT/'native/browser'/native).read_bytes():
            raise SystemExit('Current frontend differs from the accepted candidate: '+target)
    if args.output.exists() or args.patch_output.exists():raise SystemExit('Use fresh output folders.')
    shutil.copytree(source,args.output)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest['packagingSource']=commit
    manifest['packagingSourceURL']='https://github.com/tntisthebomb/BlenderIpad/tree/'+commit
    (args.output/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    proof['assets']={p.name:digest(p) for p in args.output.iterdir() if p.is_file() and p.name!='editor-validation.json'}
    proof['packagingSource']=commit
    (args.output/'editor-validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    args.patch_output.mkdir(parents=True)
    for name in manifest['overlayFiles']+['README.txt','delivery-manifest.json','editor-validation.json',
                                         'LICENSE.txt','original-engine-validation.json','original-delivery-manifest.json']:
        shutil.copyfile(args.output/name,args.patch_output/name)
    for name,expected in proof['assets'].items():
        if digest(args.output/name)!=expected:raise SystemExit('Final asset hash mismatch: '+name)
    print('PASS: exact seven-check accepted UI and engine unchanged; corrected final manifest/proof hashes and prepared full/small packages.')

if __name__=='__main__':main()
