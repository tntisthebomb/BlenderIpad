#!/usr/bin/env python3
"""Bundle only WGSL captured from an actual cold run of the current engine."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from setup_browser import ROOT,CACHE
from validate_blender_editor import ASSETS,digest
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--capture',type=Path,required=True)
 parser.add_argument('--runtime',type=Path,default=CACHE/'blender-webgpu-browser')
 args=parser.parse_args();runtime=args.runtime
 entries=json.loads(args.capture.read_text());seen=set()
 if not isinstance(entries,list) or not entries or len(entries)>500:raise SystemExit('Unexpected native shader capture size')
 for pair in entries:
  if not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) or not re.fullmatch(r'v8:[vfc]:[0-9a-f]{16}:\d+',pair[0]) or pair[0] in seen or not isinstance(pair[1],str) or not pair[1] or len(pair[1])>262144:
   raise SystemExit('Invalid or duplicate native shader translation')
  seen.add(pair[0])
 identity=json.loads((runtime/'engine_identity.json').read_text())
 if identity['sha256']!=digest(runtime/'blender-core.wasm'):raise SystemExit('Capture engine identity mismatch')
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 seed={'version':1,'schema':'v8-fnv64-length','engineSHA256':identity['sha256'],'producerSource':source,'entries':sorted(entries)}
 encoded=json.dumps(seed,separators=(',',':'))+'\n'
 if len(encoded)>2097152:raise SystemExit('Generated seed is too large')
 (runtime/'startup_shader_seed.json').write_text(encoded)
 content=hashlib.sha256()
 for name in ASSETS:
  if name=='service-worker.js':continue
  content.update(name.encode());content.update(digest(runtime/name).encode())
 worker=(ROOT/'native/browser/service-worker.js').read_text();content.update(worker.encode())
 (runtime/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__','blender-ipad-'+content.hexdigest()))
 print('Generated '+str(len(entries))+' native shader translations for '+identity['sha256']+'; refreshed coherent offline cache. Full acceptance is still required.')
