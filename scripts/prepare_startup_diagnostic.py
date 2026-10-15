#!/usr/bin/env python3
"""Add the screenshot panel to the exact previously distributed engine.

Optionally derive a lower-memory candidate by stripping debug names. Acceptance remains pending after preparation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from browser_low_memory import strip_debug_names

ROOT=Path(__file__).resolve().parents[1]
ENGINE='893f6163652f5cde223f9781a61ef4931f4b3444'
OVERLAY=('index.html','editor.html','startup_stats.js','ipad-startup.html','service-worker.js')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--low-memory',action='store_true')
    args=parser.parse_args()
    source=args.input_dir;output=args.output
    manifest=json.loads((source/'delivery-manifest.json').read_text())
    proof=json.loads((source/'editor-validation.json').read_text())
    if manifest['sourceCommit']!=ENGINE or manifest['physicalSafariAccepted'] is not False:
        raise SystemExit('Expected the exact experimental engine already installed on the iPad.')
    if manifest['acceptedAssets']!=proof['assets']:
        raise SystemExit('Original engine proof and delivery manifest disagree.')
    for name,expected in proof['assets'].items():
        if Path(name).name!=name or digest(source/name)!=expected:
            raise SystemExit('Original accepted asset changed: '+name)
    if digest(source/'ipad-update.html')!=manifest['helperSHA256']:
        raise SystemExit('Offline updater differs from its pinned source.')
    if output.exists():raise SystemExit('Use a fresh output folder; preserve existing runtimes.')
    shutil.copytree(source,output)
    (output/'editor-validation.json').rename(output/'original-engine-validation.json')
    (output/'delivery-manifest.json').rename(output/'original-delivery-manifest.json')
    for name in OVERLAY:
        if name=='service-worker.js':continue
        native='blender_editor.html' if name in ('index.html','editor.html') else name
        shutil.copyfile(ROOT/'native/browser'/native,output/name)
    transformations={}
    if args.low_memory:
        wasm,transformations=strip_debug_names((output/'blender-core.wasm').read_bytes())
        (output/'blender-core.wasm').write_bytes(wasm)
        shutil.copyfile(ROOT/'native/browser/blender_webgpu.html',output/'core.html')
    # The service worker waits for old tabs to close; all protected assets get
    # a new coherent cache, including the diagnostic script while offline.
    inputs=proof['assets'].keys() | {'startup_stats.js'}
    cache=hashlib.sha256()
    for name in sorted(set(inputs)-{'service-worker.js'}):
        cache.update(name.encode());cache.update(bytes.fromhex(digest(output/name)))
    worker=(ROOT/'native/browser/service-worker.js').read_text()
    cache.update(worker.encode())
    (output/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__','startup-stats-'+cache.hexdigest()))
    frontend=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    metadata={'profile':'experimental-startup-diagnostic','nativeEngineSource':ENGINE,
        'frontendSource':frontend,'physicalSafariAccepted':False,'validation':'pending',
        'originalNativeEngineAssets':{name:proof['assets'][name] for name in ('blender-core.js','blender-core.wasm','blender-core.data')},
        'nativeEngineAssets':{name:digest(output/name) for name in ('blender-core.js','blender-core.wasm','blender-core.data')},
        'lowMemory':args.low_memory,'transformations':transformations,
        'correspondingNativeSourceURL':manifest['correspondingSourceURL'],
        'correspondingFrontendSourceURL':'https://github.com/tntisthebomb/BlenderIpad/tree/'+frontend,
        'overlayFiles':list(OVERLAY)+(['blender-core.wasm','core.html'] if args.low_memory else [])}
    (output/'delivery-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    readme=(ROOT/'docs'/('ipad-low-memory.txt' if args.low_memory else 'ipad-startup-stats.txt')).read_text()
    (output/'README.txt').write_text(readme+'\nNative corresponding source: '+metadata['correspondingNativeSourceURL']+'\nFrontend corresponding source: '+metadata['correspondingFrontendSourceURL']+'\n')
    for name,expected in metadata['nativeEngineAssets'].items():
        if digest(output/name)!=expected:raise SystemExit('Native engine bytes changed: '+name)
    print('Prepared pending startup profile. Low-memory transformations: '+str(args.low_memory))

if __name__=='__main__':main()
