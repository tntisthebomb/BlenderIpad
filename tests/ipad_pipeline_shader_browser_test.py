#!/usr/bin/env python3
"""Validate engine-free replay of the exact delivered outline pipeline.

This tests both synchronous and async API error capture. Chromium success does
not establish that Safari compiles the pipeline or has enough RAM for Blender.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import os,json,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'native/browser')))
Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
  env=dict(os.environ);executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
  driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
  if driver.exists():env['VK_ICD_FILENAMES']=str(driver)
  browser=p.chromium.launch(executable_path=executable,env=env,args=['--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
  page=browser.new_page();requests=[];errors=[]
  page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
  page.add_init_script('''const request=GPUAdapter.prototype.requestDevice;
  GPUAdapter.prototype.requestDevice=function(...args){window.deviceRequests=(window.deviceRequests||0)+1;return request.apply(this,args)}''')
  origin=f'http://127.0.0.1:{server.server_port}'
  page.goto(origin+'/ipad-pipeline-check.html')
  assert not page.evaluate('window.deviceRequests || window.blenderEditor || window.createBlenderCore')
  assert len(requests)==1,requests
  fixture=page.evaluate('fixture')
  assert fixture['fragmentSHA256']=='90ae17e1cdfbd88290bf1a7839ba5fc30dd4889ebb09bb9f6439efa414418dd2'
  for stage in ('vertex','fragment'):
   assert hashlib.sha256(fixture['descriptor'][stage]['module']['code'].encode()).hexdigest()==fixture[stage+'SHA256']
  entries=fixture['descriptor']['layout']['bindGroupLayouts'][0]['entries']
  assert [e['binding'] for e in entries]==[128,0,1]
  assert entries[0]['sampler']['type']=='filtering' and entries[2]['buffer']['minBindingSize']==0
  assert all(e['visibility']==3 for e in entries)
  assert fixture['descriptor']['primitive']['frontFace']=='cw'
  assert fixture['descriptor']['fragment']['targets'][0]['blend']['color']['dstFactor']=='one-minus-src-alpha'
  page.locator('#check').click()
  page.wait_for_function('document.querySelector("#message").textContent.startsWith("Check finished")',timeout=45000)
  report=json.loads(page.locator('#report').input_value())
  assert len(report['results'])==4 and all(x['compiled'] for x in report['results']),report
  assert not report['errors'] and not errors,(report,errors)
  assert page.evaluate('window.deviceRequests')==2
  assert len(requests)==1 and not page.evaluate('window.blenderEditor || window.createBlenderCore')
  assert not page.evaluate('navigator.serviceWorker.controller')
  (ROOT/'.cache/ipad-pipeline-check-result.json').write_text(json.dumps(report,indent=2)+'\n')
  fake=browser.new_context()
  fake.add_init_script('''
   Object.defineProperty(navigator,'gpu',{value:{requestAdapter:async()=>{
    let consumed=false;
    return {features:new Set(['depth32float-stencil8','indirect-first-instance']),limits:{},requestDevice:async()=>{
     if(consumed)throw Error('Adapter consumed');consumed=true;
     const scopes=[];let lost;
     return Object.assign(new EventTarget(),{lost:new Promise(resolve=>lost=resolve),
      destroy(){window.destroyCount=(window.destroyCount||0)+1;lost({reason:'destroyed'});},
      createShaderModule(){return {};},createBindGroupLayout(){return {};},createPipelineLayout(){return {};},
      pushErrorScope(filter){scopes.push({filter,error:null});},popErrorScope(){return Promise.resolve(scopes.pop().error);},
      createRenderPipeline(){scopes.find(s=>s.filter==='validation').error={message:'Failed to compile the shader source, generated metal: '+('source '.repeat(8000))+' - error synchronous Metal explanation'};return {};},
      async createRenderPipelineAsync(){return {};}
     });
    }};
   }}});
   Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('denied')}}});
  ''')
  failure=fake.new_page();failure.goto(origin+'/ipad-pipeline-check.html');failure.locator('#check').click()
  failure.wait_for_function('document.querySelector("#message").textContent.startsWith("Check finished")')
  result=json.loads(failure.locator('#report').input_value())
  assert [r['compiled'] for r in result['results']]==[False,True,False,True],result
  assert result['results'][0]['errors']==['synchronous Metal explanation'],result
  assert not result['errors'] and failure.evaluate('window.destroyCount')==2
  assert failure.locator('#check').is_disabled()
  failure.locator('#copy').click();assert 'Report selected' in failure.locator('#message').inner_text()
  with failure.expect_download() as pending:failure.locator('#download').click()
  assert json.loads(Path(pending.value.path()).read_text())==result
  assert json.loads(failure.evaluate('localStorage.getItem("blender-pipeline-check-last")'))==result
  fake.close();browser.close()
finally:server.shutdown();server.server_close()
print('PASS: captured outline pipeline, sync/async compilation, default/engine devices, scoped Metal error tail, retired devices and engine-free report transfer.')
