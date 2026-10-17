#!/usr/bin/env python3
"""Stage a flat full runtime only after exact native editor acceptance."""
import json,shutil,subprocess,os
from setup_browser import ROOT,CACHE,BLENDER
from validate_blender_editor import ASSETS,snapshot,digest
if __name__=='__main__':
 runtime=CACHE/'blender-webgpu-browser';proof=json.loads((runtime/'editor-validation.json').read_text())
 if proof['profile']!='experimental-editor' or proof['physicalSafariAccepted'] is not False:raise SystemExit('Unrecognized acceptance proof')
 if snapshot()!={k:proof[k] for k in ('assets','tests')}:raise SystemExit('Candidate changed after acceptance')
 out=ROOT/'work/cooperative-runtime';out.mkdir(parents=True,exist_ok=False)
 for name in (*ASSETS,'editor-validation.json'):shutil.copyfile(runtime/name,out/name)
 shutil.copyfile(ROOT/'native/browser/LICENSE-GPL-3.0.txt',out/'LICENSE.txt')
 sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 run=os.environ.get('GITHUB_RUN_ID','local')
 (out/'README.txt').write_text((ROOT/'docs/ipad-cooperative-startup.txt').read_text()+'\nPort source: https://github.com/tntisthebomb/BlenderIpad/tree/'+sha+'\nSource bundle and checks: https://github.com/tntisthebomb/BlenderIpad/actions/runs/'+run+'\n')
 manifest={'profile':'experimental-cooperative-startup','sourceCommit':sha,'nativeUpstreamCommit':BLENDER['commit'],
 'physicalSafariAccepted':False,'validation':'automated-native-editor-checks-passed','newNativeEngine':True,
 'assets':{p.name:digest(p) for p in out.iterdir() if p.is_file()}}
 (out/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('Prepared exact accepted cooperative runtime; physical iPad startup remains unverified.')
