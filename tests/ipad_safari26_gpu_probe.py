#!/usr/bin/env python3
"""Read actual system Safari WebGPU availability; never claim engine acceptance."""
import json,platform,subprocess,time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.safari.options import Options
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def end_headers(self):
  self.send_header('Cross-Origin-Opener-Policy','same-origin')
  self.send_header('Cross-Origin-Embedder-Policy','require-corp')
  super().end_headers()
def main():
 result={'diagnostic':'system-safari26-webgpu-availability','engineStarted':False,'macOS':platform.mac_ver()[0]}
 driver=None;server=None
 try:
  subprocess.run(['sudo','safaridriver','--enable'],check=True,capture_output=True,text=True)
  with TemporaryDirectory() as directory:
   Path(directory,'index.html').write_text('<!doctype html><meta charset="utf-8"><canvas width="8" height="8"></canvas><body>Safari WebGPU readiness check</body>')
   server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory));Thread(target=server.serve_forever,daemon=True).start()
   driver=webdriver.Safari(options=Options());driver.set_script_timeout(40)
   result['browserVersion']=driver.capabilities.get('browserVersion')
   driver.get(f'http://localhost:{server.server_port}/')
   result.update(driver.execute_async_script('''const done=arguments[0];
    (async()=>{
     const r={secureContext:isSecureContext,crossOriginIsolated,webGPU:!!navigator.gpu,userAgent:navigator.userAgent};
     if(!navigator.gpu){r.status='webgpu-unavailable';return r;}
     const adapter=await navigator.gpu.requestAdapter();r.adapterAvailable=!!adapter;
     if(!adapter){r.status='adapter-unavailable';return r;}
     r.features=Array.from(adapter.features);r.adapterInfo=adapter.info?{vendor:adapter.info.vendor,architecture:adapter.info.architecture,device:adapter.info.device,description:adapter.info.description}:null;
     r.limits={maxComputeInvocationsPerWorkgroup:adapter.limits.maxComputeInvocationsPerWorkgroup,maxStorageBuffersPerShaderStage:adapter.limits.maxStorageBuffersPerShaderStage,maxStorageTexturesPerShaderStage:adapter.limits.maxStorageTexturesPerShaderStage};
     const device=await adapter.requestDevice();
     try{
      const buffer=device.createBuffer({size:4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.COPY_SRC});
      device.queue.writeBuffer(buffer,0,new Uint32Array([42]));
      device.queue.submit([device.createCommandEncoder().finish()]);
      await device.queue.onSubmittedWorkDone();
      r.commandSubmissionCompleted=true;r.status='gpu-ready';buffer.destroy();
     }finally{device.destroy();}
     return r;
    })().then(done,error=>done({status:'probe-error',error:String(error)}));'''))
 except Exception as error:
  result.update(status='probe-error',error=str(error))
 finally:
  if driver:
   try:driver.quit()
   except Exception:pass
  if server:server.shutdown();server.server_close()
 out=ROOT/'work/memory/safari26-webgpu-probe.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
 if result.get('status')=='probe-error':raise SystemExit(1)
if __name__=='__main__':main()
