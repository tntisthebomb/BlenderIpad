#!/usr/bin/env python3
"""Overlay command/recovery diagnostics on the exact accepted v4 engine."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from browser_native_stage_trace import instrument_native_stages
ROOT=Path(__file__).resolve().parents[1]
BASE='95e7feb2091f1a986e450621f201b89592713ffc'
FILES=('startup_stats.js','startup_watchdog.js','service-worker.js','index.html','editor.html','blender-core.js')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 source=args.input_dir;out=args.output
 proof=json.loads((source/'editor-validation.json').read_text());baseline=json.loads((source/'delivery-manifest.json').read_text())
 if proof['frontendSource']!=BASE or baseline['frontendSource']!=BASE or len(proof['checks'])!=13:
  raise SystemExit('Expected the exact v4 build with all thirteen acceptance checks.')
 if proof['physicalSafariAccepted'] is not False or baseline['validation']!='automated-frontend-checks-passed':raise SystemExit('Unrecognized baseline acceptance.')
 for name,expected in proof['assets'].items():
  if Path(name).name!=name or digest(source/name)!=expected:raise SystemExit('Baseline changed: '+name)
 if out.exists():raise SystemExit('Use a fresh output folder.')
 shutil.copytree(source,out)
 (out/'editor-validation.json').rename(out/'previous-editor-validation.json')
 (out/'delivery-manifest.json').rename(out/'previous-delivery-manifest.json')
 for name in FILES:
  if name not in ('service-worker.js','blender-core.js'):shutil.copyfile(ROOT/'native/browser'/('blender_editor.html' if name in ('index.html','editor.html') else name),out/name)
 before_js=digest(out/'blender-core.js')
 (out/'blender-core.js').write_text(instrument_native_stages((out/'blender-core.js').read_text()))
 cache=hashlib.sha256()
 for name in sorted(proof['assets'].keys()|{'startup_watchdog.js'}):
  if name in ('service-worker.js','delivery-manifest.json','editor-validation.json'):continue
  cache.update(name.encode());cache.update(bytes.fromhex(digest(out/name)))
 worker=(ROOT/'native/browser/service-worker.js').read_text();cache.update(worker.encode())
 (out/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__','native-stage-'+cache.hexdigest()))
 frontend=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 manifest={'profile':'experimental-native-stage-trace','version':[5,2,2],
  'frontendSource':frontend,'nativeEngineSource':baseline['nativeEngineSource'],
  'baselineNativeEngineAssets':baseline['nativeEngineAssets'],
  'nativeEngineAssets':{**baseline['nativeEngineAssets'],'blender-core.js':digest(out/'blender-core.js')},
  'runtimeJSTransformation':{'type':'bounded-native-stage-trace','before':before_js,'after':digest(out/'blender-core.js')},
  'baselineSource':BASE,
  'baselineRun':38813101042,'baselineFullArtifact':12009219523,
  'inheritedBaselineChecks':proof['checks'],'inheritedProofSHA256':digest(out/'previous-editor-validation.json'),
  'physicalSafariAccepted':False,'validation':'pending','overlayFiles':list(FILES),
  'correspondingNativeSourceURL':baseline['correspondingNativeSourceURL'],
  'correspondingEngineAdaptationSourceURL':baseline['correspondingFrontendSourceURL'],
  'correspondingFrontendSourceURL':'https://github.com/tntisthebomb/BlenderIpad/tree/'+frontend}
 for name,expected in manifest['nativeEngineAssets'].items():
  if digest(out/name)!=expected:raise SystemExit('Engine changed: '+name)
 (out/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (out/'README.txt').write_text((ROOT/'docs/ipad-native-stage-trace.txt').read_text()+'\nNative source: '+manifest['correspondingNativeSourceURL']+'\nEngine adaptation source: '+manifest['correspondingEngineAdaptationSourceURL']+'\nDiagnostics source: '+manifest['correspondingFrontendSourceURL']+'\n')
 print('Prepared pending diagnostics; v4 WASM/data byte-identical; bounded JS bridge trace added.')
if __name__=='__main__':main()
