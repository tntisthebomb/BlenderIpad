#!/usr/bin/env python3
"""Validate the overlay against the actual distributed native engine."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'.cache/blender-webgpu-browser'
TESTS=('tests/wasm_mime_browser_test.py','tests/startup_stats_browser_test.py','tests/startup_preflight_browser_test.py',
       'tests/editor_install_failure_test.py','tests/editor_files_browser_test.py',
       'tests/offline_shell_browser_test.py','tests/blender_tablet_startup_browser_test.py',
       'tests/blender_editor_browser_test.py')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def assets():return {p.name:digest(p) for p in RUNTIME.iterdir() if p.is_file()}

def main():
    manifest=json.loads((RUNTIME/'delivery-manifest.json').read_text())
    if manifest['profile']!='experimental-startup-diagnostic' or manifest['validation']!='pending':
        raise SystemExit('Expected a fresh pending diagnostic overlay.')
    before=assets()
    checks=[(test,[]) for test in TESTS]
    if manifest.get('lowMemory'):
        checks += [('tests/blender_editor_browser_test.py',['--tablet']),
                   ('tests/blender_modeling_browser_test.py',['--tablet'])]
        checks += [('tests/blender_render_browser_test.py',['--tablet','--engine',engine])
                   for engine in ('BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES')]
    for test,args in checks:
        subprocess.run([sys.executable,str(ROOT/test),*args],cwd=ROOT,check=True)
    if before!=assets():raise SystemExit('Runtime changed during its acceptance tests.')
    for name,expected in manifest['nativeEngineAssets'].items():
        if digest(RUNTIME/name)!=expected:raise SystemExit('Native engine changed: '+name)
    manifest['validation']='automated-frontend-checks-passed'
    (RUNTIME/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    proof={'profile':'experimental-startup-diagnostic','version':[5,2,2],
        'checks':[{'test':test,'args':args} for test,args in checks],'assets':assets(),
        'tests':{test:digest(ROOT/test) for test,_ in checks},
        'nativeEngineSource':manifest['nativeEngineSource'],
        'frontendSource':manifest['frontendSource'],'lowMemory':manifest.get('lowMemory',False),'physicalSafariAccepted':False}
    (RUNTIME/'editor-validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    patch=ROOT/'work/startup-stats-update';patch.mkdir(parents=True,exist_ok=False)
    for name in manifest['overlayFiles']:shutil.copyfile(RUNTIME/name,patch/name)
    for name in ('README.txt','delivery-manifest.json','editor-validation.json','LICENSE.txt',
                 'original-engine-validation.json','original-delivery-manifest.json'):
        shutil.copyfile(RUNTIME/name,patch/name)
    print('PASS: actual native editor, persistent stats, tablet startup, files, recovery and offline updates. Physical iPad acceptance remains pending.')

if __name__=='__main__':main()
