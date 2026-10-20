#!/usr/bin/env python3
"""Reuse immutable accepted dependencies without reinstalling unchanged headers."""
import hashlib,json,os,subprocess
from pathlib import Path
from setup_browser import ROOT,CACHE
BASE='7f940bc0fa86c69216122b6407c57acee0477d9b'
BASE_WASM='030dc759384833564f48f5b2aa18f7c574405fcd532d90da698f138ef9cefbf4'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
if __name__=='__main__':
 changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
 def affects_dependencies(name):
  return (name in ('port.lock.json','browser-port.lock.json','scripts/setup_browser.py') or
   name.startswith(('scripts/build_browser_','cmake/','native/browser/GHOST','native/browser/expr_math_errors')) or
   name.startswith(('native/browser/python_startup_yield_probe','native/browser/startup_yield_probe','native/browser/ghost_probe','native/browser/ghost_webgpu_probe')))
 unsafe=[name for name in changed if affects_dependencies(name)]
 proof_path=CACHE/'accepted-native-dependencies.json'
 prefix=CACHE/'wasm-threaded-sysroot'
 files=sorted(p for folder in ('include','lib') for p in (prefix/folder).rglob('*') if p.is_file()) if prefix.is_dir() else []
 recorded=json.loads(proof_path.read_text()) if proof_path.exists() else None
 base_runtime=CACHE/'blender-webgpu-browser/blender-core.wasm'
 restored=os.environ.get('RESTORED_NATIVE_CACHE','')
 trusted=bool(recorded and recorded.get('source')==BASE)
 if not trusted and restored.endswith('-'+BASE) and base_runtime.exists():trusted=digest(base_runtime)==BASE_WASM
 reuse=False
 if trusted and not unsafe and files:
  hashes={str(p.relative_to(CACHE)):digest(p) for p in files}
  if recorded is None or recorded.get('files')==hashes:
   proof_path.write_text(json.dumps({'source':BASE,'files':hashes},sort_keys=True)+'\n');reuse=True
 value='true' if reuse else 'false'
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('reuse='+value+'\n')
 print('Accepted dependency reuse: '+value)
 if unsafe:print('Dependency inputs changed: '+', '.join(unsafe))
 if reuse:print('Content hashes verified; unchanged dependency headers will retain their original timestamps. Changed Blender inputs still rebuild and all editor acceptance checks still run.')
