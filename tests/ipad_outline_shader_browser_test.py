#!/usr/bin/env python3
"""Validate the engine-free Safari repro and each variant's actual outline pixels.

Chromium acceptance checks semantics; it does not establish Metal compilation.
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
  env=dict(os.environ)
  executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
  driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
  if driver.exists():env['VK_ICD_FILENAMES']=str(driver)
  browser=p.chromium.launch(executable_path=executable,env=env,args=['--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
  page=browser.new_page();requests=[];errors=[]
  page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
  page.add_init_script('''const request=GPUAdapter.prototype.requestDevice;
  GPUAdapter.prototype.requestDevice=function(...args){window.deviceRequests=(window.deviceRequests||0)+1;return request.apply(this,args)}''')
  page.goto(f'http://127.0.0.1:{server.server_port}/ipad-shader-check.html')
  assert not page.evaluate('window.deviceRequests || window.blenderEditor || window.createBlenderCore')
  assert len(requests)==1,requests
  cases=page.evaluate('cases')
  for c in cases:assert hashlib.sha256(c['code'].encode()).hexdigest()==c['sha256']
  page.locator('#check').click();page.wait_for_function('document.querySelector("#message").textContent.startsWith("Check finished")',timeout=45000)
  report=json.loads(page.locator('#report').input_value())
  assert len(report['results'])==4 and all(x['compiled'] for x in report['results']),report
  assert not report['errors'] and not errors,(report,errors)
  assert len(requests)==1 and not page.evaluate('window.blenderEditor || window.createBlenderCore'),requests
  assert not page.evaluate('navigator.serviceWorker.controller')
  results=page.evaluate('''async()=>{
   const adapter=await navigator.gpu.requestAdapter();const d=await adapter.requestDevice();const n=8;
   const layout=d.createBindGroupLayout({entries:[
    {binding:0,visibility:GPUShaderStage.FRAGMENT,texture:{sampleType:'uint'}},
    {binding:1,visibility:GPUShaderStage.FRAGMENT,buffer:{type:'uniform',minBindingSize:352}},
    {binding:128,visibility:GPUShaderStage.FRAGMENT,sampler:{type:'non-filtering'}}]});
   const pl=d.createPipelineLayout({bindGroupLayouts:[layout]});
   const v=d.createShaderModule({code:`@vertex fn main(@builtin(vertex_index)i:u32)->@builtin(position)vec4<f32>{
    return vec4<f32>(f32((i<<1u)&2u)*2.-1.,f32(i&2u)*2.-1.,0.,1.);}`});
   const uniform=d.createBuffer({size:352,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
   const values=new Float32Array(88);values.set([1/n,1/n],2);values.set([.8,.4,.2,1],4);values[78]=1;
   d.queue.writeBuffer(uniform,0,values);
   const ids=d.createTexture({size:[n,n],format:'r32uint',usage:GPUTextureUsage.COPY_DST|GPUTextureUsage.TEXTURE_BINDING});
   const pixels=new Uint32Array(64*n);for(let y=2;y<6;y++)for(let x=2;x<6;x++)pixels[y*64+x]=7;
   d.queue.writeTexture({texture:ids},pixels,{bytesPerRow:256},[n,n]);
   const group=d.createBindGroup({layout,entries:[{binding:0,resource:ids.createView()},{binding:1,resource:{buffer:uniform}},{binding:128,resource:d.createSampler()}]});
   const results=[];
   try{for(const c of cases){
    const pipeline=await d.createRenderPipelineAsync({layout:pl,vertex:{module:v,entryPoint:'main'},fragment:{module:d.createShaderModule({code:c.code}),entryPoint:'main',targets:[{format:'rgba8unorm'}]}});
    const target=d.createTexture({size:[n,n],format:'rgba8unorm',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
    const output=d.createBuffer({size:256*n,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
    const encoder=d.createCommandEncoder();const pass=encoder.beginRenderPass({colorAttachments:[{view:target.createView(),clearValue:[0,0,0,0],loadOp:'clear',storeOp:'store'}]});
    pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.draw(3);pass.end();encoder.copyTextureToBuffer({texture:target},{buffer:output,bytesPerRow:256},[n,n]);d.queue.submit([encoder.finish()]);
    await output.mapAsync(GPUMapMode.READ);const raw=new Uint8Array(output.getMappedRange());const packed=[];
    for(let y=0;y<n;y++)packed.push(...raw.slice(y*256,y*256+n*4));
    results.push({name:c.name,pixels:packed});output.unmap();output.destroy();target.destroy();
   }}finally{ids.destroy();uniform.destroy();d.destroy();}return results;
  }''')
  def value(x,y):return 7 if 2<=x<6 and 2<=y<6 else 0
  expected=[]
  for y in range(8):
   for x in range(8):
    center=value(x,y)
    alpha=sum(value(max(0,min(7,x+dx)),max(0,min(7,y+dy)))!=center for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)))/4
    expected += [round(channel*alpha*255) for channel in (.8,.4,.2,1)]
  for result in results:
   assert len(result['pixels'])==len(expected)
   assert all(abs(a-b)<=1 for a,b in zip(result['pixels'],expected)),(result['name'],result['pixels'],expected)
  (ROOT/'.cache/ipad-outline-check-result.json').write_text(json.dumps({'compiler':report,'numeric':[{'name':r['name'],'pixels':len(r['pixels'])} for r in results]},indent=2)+'\n')
  print('PASS: exact delivered shader + three diagnostic variants compile and preserve all 256 outline channels; no engine, network fetches, workers or offline registration in diagnostic.')
  fixture=browser.new_context()
  fixture.add_init_script("""
    let lostResolve;let calls=0;
    const device=Object.assign(new EventTarget(),{
      lost:new Promise(resolve=>lostResolve=resolve),
      destroy(){window.destroyCount=(window.destroyCount||0)+1;lostResolve({reason:'destroyed'});},
      createShaderModule(){return {};},createBindGroupLayout(){return {};},createPipelineLayout(){return {};},
      async createRenderPipelineAsync(){
        if(++calls===1)throw new Error('Failed to compile the shader source, generated metal: '+('source '.repeat(8000))+' - error program_source:42: compiler explanation');
        return {};
      }
    });
    Object.defineProperty(navigator,'gpu',{value:{requestAdapter:async()=>({requestDevice:async()=>device})}});
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('denied')}}});
  """)
  diagnostic=fixture.new_page()
  diagnostic.goto(f'http://127.0.0.1:{server.server_port}/ipad-shader-check.html')
  diagnostic.locator('#check').click()
  diagnostic.wait_for_function('document.querySelector("#message").textContent.startsWith("Check finished")')
  failed=json.loads(diagnostic.locator('#report').input_value())
  assert failed['results'][0]['error']=='program_source:42: compiler explanation',failed
  assert failed['results'][0]['compiled'] is False and all(r['compiled'] for r in failed['results'][1:])
  assert not failed['errors'] and diagnostic.evaluate('window.destroyCount')==1
  assert diagnostic.locator('#check').is_disabled()
  diagnostic.locator('#copy').click()
  assert 'Report selected' in diagnostic.locator('#message').inner_text()
  with diagnostic.expect_download() as pending:diagnostic.locator('#download').click()
  assert json.loads(Path(pending.value.path()).read_text())==failed
  assert json.loads(diagnostic.evaluate('localStorage.getItem("blender-outline-check-last")'))==failed
  fixture.close()
  assert not errors,errors
  browser.close()
finally:server.shutdown();server.server_close()
