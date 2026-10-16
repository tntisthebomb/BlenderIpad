#!/usr/bin/env python3
"""Validate the new diagnostics; retain the exact accepted v4 engine proof."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
from validate_startup_diagnostic import TESTS
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'.cache/blender-webgpu-browser'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def assets():return {p.name:digest(p) for p in RUNTIME.iterdir() if p.is_file()}
def main():
 manifest=json.loads((RUNTIME/'delivery-manifest.json').read_text())
 if manifest['profile']!='experimental-native-stage-trace' or manifest['validation']!='pending':raise SystemExit('Expected a fresh diagnostic overlay.')
 before=assets();checks=[(test,[]) for test in TESTS]
 checks += [('tests/startup_watchdog_browser_test.py',[]),('tests/blender_editor_browser_test.py',['--tablet']),
  ('tests/blender_modeling_browser_test.py',['--tablet'])]
 checks += [('tests/blender_render_browser_test.py',['--tablet','--engine',engine])
  for engine in ('BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES')]
 for test,args in checks:
  print('RUN: '+test+' '+' '.join(args),flush=True)
  subprocess.run([sys.executable,str(ROOT/test),*args],cwd=ROOT,check=True)
 if before!=assets():raise SystemExit('Runtime changed during acceptance.')
 for name,expected in manifest['nativeEngineAssets'].items():
  if digest(RUNTIME/name)!=expected:raise SystemExit('Engine changed: '+name)
 manifest['validation']='automated-native-stage-checks-passed'
 (RUNTIME/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 proof={'profile':manifest['profile'],'frontendSource':manifest['frontendSource'],
  'nativeEngineSource':manifest['nativeEngineSource'],'physicalSafariAccepted':False,
  'baselineSource':manifest['baselineSource'],'inheritedBaselineChecks':manifest['inheritedBaselineChecks'],
  'checks':[{'test':test,'args':args} for test,args in checks],
  'tests':{test:digest(ROOT/test) for test,_ in checks},'assets':assets()}
 (RUNTIME/'editor-validation.json').write_text(json.dumps(proof,indent=2)+'\n')
 patch=ROOT/'work/native-stage-trace-update';patch.mkdir(parents=True,exist_ok=False)
 for name in manifest['overlayFiles']+['README.txt','delivery-manifest.json','editor-validation.json',
   'previous-editor-validation.json','previous-delivery-manifest.json','LICENSE.txt']:
  shutil.copyfile(RUNTIME/name,patch/name)
 print('PASS: command trace, independent recovery recorder, actual editor/tablet input, persistence and offline updates. Native modeling, Workbench, Eevee and CPU Cycles were tested again; physical iPad startup remains unverified.')
if __name__=='__main__':main()
