#!/usr/bin/env python3
"""Investigate the accepted native engine using installed Safari and Metal."""
import argparse,faulthandler,hashlib,json,platform,shutil,subprocess,time
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event,Thread
from selenium import webdriver
from selenium.webdriver.safari.service import Service
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);args=p.parse_args()
faulthandler.dump_traceback_later(330,exit=True)
output=ROOT/'work/native-system-safari';output.mkdir(parents=True,exist_ok=True)
report={'physicalIPad':False,'browser':'system Safari','status':'preparing','engineLoaded':False,'platform':platform.platform()}
def save(): (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
save();source=args.input_dir;proof=json.loads((source/'editor-validation.json').read_text())
assert proof['frontendSource']=='efa58b78152b449e92597820f4d0fa20b5d8e4ca'
assert len(proof['checks'])==10 and proof['physicalSafariAccepted'] is False
for name,expected in proof['assets'].items():assert sha(source/name)==expected,name
report['processMemoryNote']='RSS sums may count shared pages more than once; not total device RAM.'
report['baselineSource']=proof['frontendSource'];report['nativeEngineAssets']=json.loads((source/'delivery-manifest.json').read_text())['nativeEngineAssets'];save()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*unused):pass
 def end_headers(self):
  self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp');super().end_headers()
with TemporaryDirectory(dir=ROOT/'.cache',prefix='system-safari-') as temp:
 base=Path(temp)/'runtime';shutil.copytree(source,base)
 # Force the existing tablet startup path; do not modify JS/WASM/data engine bytes.
 for name in ('index.html','editor.html'):
  text=(base/name).read_text();needle="const tabletMode=/iPad|iPhone|iPod/.test(navigator.userAgent) ||\n  (/Mac/.test(navigator.platform) && navigator.maxTouchPoints>1);"
  assert text.count(needle)==1; (base/name).write_text(text.replace(needle,'const tabletMode=true;'))
 for name,expected in report['nativeEngineAssets'].items():assert sha(base/name)==expected,name
 (base/'safari-gpu-probe.html').write_text('''<!doctype html><meta charset="utf-8"><canvas width="64" height="64"></canvas><script>
window.probe={phase:'starting',secure:isSecureContext,isolated:crossOriginIsolated,webGPU:!!navigator.gpu,ua:navigator.userAgent};
(async()=>{if(!navigator.gpu){probe.phase='webgpu-unavailable';return;}
 const adapter=await navigator.gpu.requestAdapter();if(!adapter){probe.phase='adapter-unavailable';return;}
 probe.features=[...adapter.features];probe.info={vendor:adapter.info?.vendor,device:adapter.info?.device,description:adapter.info?.description};
 const device=await adapter.requestDevice(),context=document.querySelector('canvas').getContext('webgpu');
 device.addEventListener('uncapturederror',e=>{probe.error=e.error.message;probe.phase='gpu-error';});
 context.configure({device,format:navigator.gpu.getPreferredCanvasFormat()});
 const encoder=device.createCommandEncoder(),pass=encoder.beginRenderPass({colorAttachments:[{view:context.getCurrentTexture().createView(),clearValue:{r:0.2,g:0.4,b:0.8,a:1},loadOp:'clear',storeOp:'store'}]});
 pass.end();device.queue.submit([encoder.finish()]);await device.queue.onSubmittedWorkDone();
 await new Promise(requestAnimationFrame);probe.phase='submitted-and-completed';
})().catch(e=>{probe.phase='error';probe.error=String(e);});</script>''')
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(base)))
 Thread(target=server.serve_forever,daemon=True).start();driver=None
 stop=Event()
 def monitor_memory():
  with (output/'process-memory.jsonl').open('w') as file:
   while not stop.is_set():
    try:
     rows=subprocess.check_output(['ps','-axo','pid=,rss=,comm='],text=True,timeout=5).splitlines();processes=[]
     for row in rows:
      parts=row.split(None,2)
      if len(parts)==3 and any(key in parts[2] for key in ('Safari','WebKit')):
       processes.append({'pid':int(parts[0]),'rssKiB':int(parts[1]),'command':parts[2]})
     file.write(json.dumps({'time':time.time(),'rssSumKiB':sum(x['rssKiB'] for x in processes),'processes':processes})+'\n');file.flush()
    except Exception:pass
    stop.wait(1)
 monitor=Thread(target=monitor_memory,daemon=True);monitor.start()
 try:
  report['status']='launching Safari';save();print(report['status'],flush=True)
  driver=webdriver.Safari(service=Service(log_output=str(output/'safaridriver.log')))
  driver.set_window_size(1180,820)
  report['capabilities']=driver.capabilities;save();driver.set_page_load_timeout(40);driver.set_script_timeout(180)
  origin=f'http://127.0.0.1:{server.server_port}';driver.get(origin+'/safari-gpu-probe.html')
  driver.execute_async_script("const done=arguments[0],start=Date.now();const t=setInterval(()=>{if(!['starting'].includes(probe.phase)||Date.now()-start>30000){clearInterval(t);done(probe);}},100);")
  report['gpuProbe']=driver.execute_script('return probe');save();print('Safari GPU:',json.dumps(report['gpuProbe']),flush=True)
  if report['gpuProbe']['phase']!='submitted-and-completed':report['status']='graphics-probe-blocked';save()
  else:
   driver.get_screenshot_as_file(str(output/'gpu-probe.png'))
   driver.get(origin+'/');report['status']='starting native engine';save();began=time.monotonic()
   # Keep one outstanding asynchronous command while native compilation can
   # block the page. The WebDriver's script timeout supplies an external bound.
   result=driver.execute_async_script('''const done=arguments[0];
    const deadline=Date.now()+150000;
    const timer=setInterval(()=>{if(document.body.dataset.rendered||document.body.dataset.error||Date.now()>deadline){clearInterval(timer);
     done({rendered:document.body.dataset.rendered||false,error:document.body.dataset.error||null,stats:window.blenderStartupStats?.snapshot(),device:window.blenderDeviceReport,logs:(window.editorOutput||[]).slice(-30)});}},250);
    const start=document.getElementById('start-editor');if(start&&!start.hidden)start.click();
   ''')
   report['wallSeconds']=round(time.monotonic()-began,2);report['snapshot']=result
   report['engineLoaded']=result.get('rendered')=='true';report['status']='viewport-presented' if report['engineLoaded'] else 'native-startup-incomplete';save()
   print('Safari native result:',report['status'],report['wallSeconds'],flush=True)
   driver.get_screenshot_as_file(str(output/'native-viewport.png'))
 except Exception as error:
  report['status']='runner-error';report['runnerError']=str(error)[:5000];save();print('Safari runner error:',str(error)[:2000],flush=True)
 finally:
  save()
  if driver:
   try:driver.quit()
   except Exception:pass
  stop.set();monitor.join(timeout=2);server.shutdown();server.server_close()
faulthandler.cancel_dump_traceback_later();print('Evidence saved:',output,flush=True)
