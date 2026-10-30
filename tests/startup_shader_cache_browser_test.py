#!/usr/bin/env python3
"""Validate exact-engine seed acceptance and native-compiler fallback paths."""
import argparse,json,os,shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
args=parser.parse_args()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
with TemporaryDirectory(dir=ROOT/'.cache',prefix='shader-seed-') as tmp:
 base=Path(tmp);seed=json.loads((ROOT/'native/browser/startup_shader_seed.json').read_text())
 for name in ('startup_shaders.js','startup_shader_seed.json'):shutil.copyfile(ROOT/'native/browser'/name,base/name)
 (base/'engine_identity.json').write_text(json.dumps({'sha256':seed['engineSHA256']}))
 (base/'index.html').write_text('<!doctype html><body><script src="startup_shaders.js"></script></body>')
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=tmp));Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=getattr(p,args.browser).launch(**({'executable_path':os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),'args':['--no-sandbox']} if args.browser=='chromium' else {}))
   context=browser.new_context();errors=[]
   def page():
    v=context.new_page();v.on('pageerror',lambda e:errors.append(str(e)))
    v.goto(f'http://127.0.0.1:{server.server_port}/');return v
   v=page();r=v.evaluate('prepareBlenderStartupShaders()')
   assert r['status']=='native translations loaded' and r['entries']==len(seed['entries']),r
   key,value=seed['entries'][0]
   assert v.evaluate('key=>__WGSL_CACHE__.get(key)',key)==value
   assert v.evaluate('__WGSL_CACHE__.get("missing")===undefined')
   assert v.evaluate('blenderStartupShaderCacheReport.hits===1&&blenderStartupShaderCacheReport.misses===1')
   assert v.evaluate('()=>{__WGSL_CACHE__.set("new-native-variant","translated");return __WGSL_CACHE__.get("new-native-variant")}')=='translated'
   assert r['persistence']=='enabled' and r['stored']==0,r
   # The native cache-put hook persists a new translation for this exact engine.
   variant=['v8:f:0123456789abcdef:42','@fragment fn main() {}']
   v.evaluate('([k,value])=>{__WGSL_CACHE__.set(k,value);__WGSL_CACHE_PUT__(k,value);__WGSL_CACHE_PUT__("invalid key",value);return blenderFlushNativeShaderCache()}',variant)
   assert v.evaluate('blenderStartupShaderCacheReport.persisted')==1
   v.close()
   v=page();r=v.evaluate('prepareBlenderStartupShaders()')
   assert r['status']=='native translations loaded' and r['stored']==1,r
   assert v.evaluate('k=>__WGSL_CACHE__.get(k)',variant[0])==variant[1]
   assert v.evaluate('__WGSL_CACHE__.get("invalid key")===undefined')
   v.close()
   context.route('**/engine_identity.json',lambda route:route.fulfill(json={'sha256':'0'*64}))
   v=page();r=v.evaluate('prepareBlenderStartupShaders()');assert r['status'].startswith('engine mismatch'),r
   assert v.evaluate('typeof __WGSL_CACHE__==="undefined"');v.close();context.unroute('**/engine_identity.json')
   context.route('**/startup_shader_seed.json',lambda route:route.fulfill(status=404,body='missing'))
   v=page();r=v.evaluate('prepareBlenderStartupShaders()');assert r['status'].startswith('seed unavailable'),r
   assert v.evaluate('typeof __WGSL_CACHE__==="undefined"');v.close();context.unroute('**/startup_shader_seed.json')
   corrupt={**seed,'entries':[seed['entries'][0],seed['entries'][0]]}
   context.route('**/startup_shader_seed.json',lambda route:route.fulfill(json=corrupt))
   v=page();r=v.evaluate('prepareBlenderStartupShaders()');assert r['status'].startswith('seed unavailable'),r
   assert v.evaluate('typeof __WGSL_CACHE__==="undefined"');v.close();context.unroute('**/startup_shader_seed.json')
   v=page();r=v.evaluate('()=>{blenderDisableStartupShaderCache=true;return prepareBlenderStartupShaders()}')
   assert r['status']=='disabled for validation',r
   assert not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS: '+args.browser+' exact-engine native shader seed, persisted session translations, real cache lookup/miss semantics, engine mismatch, missing/corrupt seed and disabled-cache fallback (no native GPU loaded in this fixture).')
