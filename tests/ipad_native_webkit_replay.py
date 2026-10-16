#!/usr/bin/env python3
"""Investigation only: replay the accepted engine with precise C/JS handoff logs."""
import argparse,faulthandler,hashlib,json,os,shutil,sys,time
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True)
p.add_argument('--registry',choices=('array','dictionary'),required=True)
p.add_argument('--browser',choices=('webkit','chromium'),default='webkit');args=p.parse_args()
faulthandler.dump_traceback_later(240,exit=True)
def sha(data):return hashlib.sha256(data).hexdigest()
source=args.input_dir;proof=json.loads((source/'editor-validation.json').read_text())
assert proof['frontendSource']=='efa58b78152b449e92597820f4d0fa20b5d8e4ca'
assert len(proof['checks'])==10 and proof['physicalSafariAccepted'] is False
for name,expected in proof['assets'].items():assert sha((source/name).read_bytes())==expected,name
report_dir=ROOT/'work/native-webkit-replay'/args.registry;report_dir.mkdir(parents=True,exist_ok=True)
report={'registry':args.registry,'browser':args.browser,'physicalIPad':False,'engineLoaded':False,
 'baselineSource':proof['frontendSource'],'status':'preparing','bridgeEvents':[],'pageErrors':[]}
def save(): (report_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*unused):pass
with TemporaryDirectory(dir=ROOT/'.cache',prefix='native-replay-') as temp:
 base=Path(temp)/'runtime';shutil.copytree(source,base)
 js=(base/'blender-core.js').read_text()
 original='''  var ptr = _emwgpuCreateCommandBuffer(0);
  WebGPU.Internals.jsObjectInsert(ptr, commandEncoder.finish());
  return ptr;'''
 replacement='''  var ptr = _emwgpuCreateCommandBuffer(0);
  browserBridgeTrace('command-buffer-allocated', ptr);
  var commandBuffer = commandEncoder.finish();
  browserBridgeTrace('finish-returned', ptr);
  WebGPU.Internals.jsObjectInsert(ptr, commandBuffer);
  browserBridgeTrace('command-buffer-registered', ptr);
  return ptr;'''
 assert js.count(original)==1;js=js.replace(original,replacement)
 trace="""var browserBridgeCount = 0;
var browserBridgeTrace = (name, ptr) => {
  if (browserBridgeCount++ < 64) {
    const message = 'BRIDGE ' + name + ' ptr=' + (ptr >>> 0) +
      ' registry=' + (Array.isArray(WebGPU.Internals.jsObjects) ? 'array' : 'dictionary') +
      ' arrayLength=' + (WebGPU.Internals.jsObjects.length ?? 'none');
    Module['printErr']?.(message);console.info(message);
  }
};
"""
 needle='var _wgpuCommandEncoderFinish = (encoderPtr, descriptor) => {'
 assert js.count(needle)==1;js=js.replace(needle,trace+needle)
 needle='var _wgpuQueueSubmit = (queuePtr, commandCount, commands) => {'
 assert js.count(needle)==1;js=js.replace(needle,needle+"\n  browserBridgeTrace('queue-submit-enter', queuePtr);")
 needle='  queue.submit(cmds);';assert js.count(needle)==1
 js=js.replace(needle,"  browserBridgeTrace('queue-submit-resolved', queuePtr);\n"+needle+"\n  browserBridgeTrace('queue-submit-returned', queuePtr);")
 assert js.count('    jsObjects: [],')==1
 if args.registry=='dictionary':js=js.replace('    jsObjects: [],','    jsObjects: Object.create(null),')
 (base/'blender-core.js').write_text(js)
 # Preserve all existing registration/release/get paths and the exact WASM.
 report['runtimeJSsha256']=sha(js.encode());report['wasmSHA256']=sha((base/'blender-core.wasm').read_bytes())
 for name,expected in json.loads((base/'delivery-manifest.json').read_text())['nativeEngineAssets'].items():
  if name!='blender-core.js':assert sha((base/name).read_bytes())==expected,name
 # An investigation-only cache key prevents accidental reuse of the other variant.
 sw=(base/'service-worker.js').read_text();sw=sw.replace('const CACHE=`','const CACHE=`replay-'+args.registry+'-')
 (base/'service-worker.js').write_text(sw)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(base)))
 Thread(target=server.serve_forever,daemon=True).start();save()
 try:
  with sync_playwright() as playwright:
   if args.browser=='webkit':
    # WKPreferences reads WebKitDebug + WebGPUEnabled from NSUserDefaults.
    # Foundation's argument domain enables it for this process only.
    preference_args=['-WebKitDebugWebGPUEnabled','YES'] if sys.platform=='darwin' else []
    report['webGPUPreferenceRequested']=bool(preference_args);save()
    context=playwright.webkit.launch_persistent_context(str(Path(temp)/'profile'),args=preference_args,viewport={'width':1180,'height':760},device_scale_factor=2,has_touch=True)
    browser=context.browser
   else:
    executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium');env=dict(os.environ)
    driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
    if driver.exists():env['VK_ICD_FILENAMES']=str(driver)
    browser=playwright.chromium.launch(executable_path=executable,env=env,args=['--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    context=browser.new_context(viewport={'width':1180,'height':760},device_scale_factor=2,has_touch=True)
   context.add_init_script("""Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});
Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});
if(typeof GPUAdapter!=='undefined'){
 const original=GPUAdapter.prototype.requestDevice;
 GPUAdapter.prototype.requestDevice=function(options={}){return original.call(this,{...options,
  requiredFeatures:(options.requiredFeatures||[]).filter(f=>f!=='float32-filterable')});};
}""")
   page=context.new_page();page.set_default_timeout(20000)
   output=(report_dir/'console.jsonl').open('w')
   def console(message):
    text=message.text;output.write(json.dumps({'type':message.type,'text':text[:5000]})+'\n');output.flush()
    if 'BRIDGE ' in text and len(report['bridgeEvents'])<64:
     report['bridgeEvents'].append(text[:500]);save()
   page.on('console',console);page.on('pageerror',lambda e:report['pageErrors'].append(str(e)[:1000]))
   origin=f'http://127.0.0.1:{server.server_port}'
   page.goto(origin+'/');page.wait_for_selector('#start-editor',state='visible')
   report['browserInfo']=page.evaluate('({ua:navigator.userAgent,webGPU:!!navigator.gpu,isolated:crossOriginIsolated})');save()
   if not report['browserInfo']['webGPU']:
    report['status']='webgpu-unavailable';save();print(json.dumps(report),flush=True)
   else:
    report['status']='starting';save();began=time.monotonic();page.locator('#start-editor').click()
    try:
     page.wait_for_function('document.body.dataset.rendered || document.body.dataset.error',timeout=120000)
     report['snapshot']=page.evaluate('({rendered:document.body.dataset.rendered,error:document.body.dataset.error,stats:blenderStartupStats.snapshot(),device:blenderDeviceReport})')
     report['engineLoaded']=report['snapshot']['rendered']=='true'
     report['status']='viewport-presented' if report['engineLoaded'] else 'startup-error'
     if report['engineLoaded']:page.locator('#canvas').screenshot(path=str(report_dir/'viewport.png'),timeout=5000)
    except Exception as error:report['status']='startup-timeout';report['waitError']=str(error)[:1000]
    report['wallSeconds']=round(time.monotonic()-began,2);save()
    print('Replay result:',args.registry,report['status'],report['wallSeconds'],flush=True)
    # Close the busy tab before touching OPFS; recover through the ordinary
    # gated startup screen without starting a second engine.
    page.close();restored=context.new_page();restored.goto(origin+'/')
    try:
     restored.wait_for_function('blenderStartupStats.previousRecovery()',timeout=10000)
     report['recovery']=restored.evaluate('({checkpoint:blenderStartupStats.previousAttempt(),worker:blenderStartupStats.previousRecovery(),text:document.querySelector("#startup-stats-text").textContent})')
     restored.locator('#startup-stats').screenshot(path=str(report_dir/'recovery.png'),timeout=5000)
    except Exception as error:report['recoveryError']=str(error)[:1000]
    save()
   context.close();browser.close();output.close()
 finally:save();server.shutdown();server.server_close()
faulthandler.cancel_dump_traceback_later()
print('INVESTIGATION SAVED:',report_dir,flush=True)
