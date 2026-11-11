#!/usr/bin/env python3
"""Execute actual Blender GPU resources and drawing through its own Python API."""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        super().end_headers()
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'.cache/blender-webgpu-browser')))
Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as playwright:
        executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
        environment=dict(os.environ)
        driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
        if driver.exists(): environment['VK_ICD_FILENAMES']=str(driver)
        browser=playwright.chromium.launch(executable_path=executable,env=environment,args=[
            '--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        context=browser.new_context()
        context.add_init_script('''window.nativeDepthTargets=[];
          const createTexture=GPUDevice.prototype.createTexture;
          GPUDevice.prototype.createTexture=function(desc){
            const texture=createTexture.call(this,desc);
            if(texture.format==='depth32float-stencil8'&&texture.height===13&&[17,19,21].includes(texture.width))nativeDepthTargets.push(texture);
            return texture;
          };
          const request=GPUAdapter.prototype.requestDevice;
          GPUAdapter.prototype.requestDevice=function(options={}) {
            return request.call(this,{...options,requiredFeatures:
              [...(options.requiredFeatures || [])].filter(feature=>feature!=='float32-filterable')}).then(device=>{window.nativeTestDevice=device;return device;});
          };''')
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        diagnostics=(ROOT/'.cache/blender-gpu-browser-console.log').open('w')
        page.on('console',lambda message: (diagnostics.write(message.type+': '+message.text+'\n'), diagnostics.flush()))
        debug_session=context.new_cdp_session(page)
        debug_session.send('Inspector.enable')
        debug_session.on('Inspector.targetCrashed',lambda event: (diagnostics.write('target-crash: '+json.dumps(event)+'\n'), diagnostics.flush()))
        page.goto(f'http://127.0.0.1:{server.server_port}/core.html')
        page.wait_for_function('document.body.dataset.ready || document.body.dataset.error',timeout=300000)
        assert page.locator('body').get_attribute('data-ready')=='true',page.locator('body').get_attribute('data-error')
        assert page.evaluate('crossOriginIsolated && !nativeTestDevice.features.has("float32-filterable")')
        page.evaluate('source=>blenderCore.FS.writeFile("/gpu_test.py",source)',(ROOT/'tests/blender_gpu_scene.py').read_text())
        context.set_offline(True)
        page.evaluate('runGPUScene()')
        page.wait_for_function('coreExit !== null || document.body.dataset.error',timeout=300000)
        assert page.evaluate('coreExit')==0,page.evaluate('coreErrors')
        checks=json.loads(page.evaluate("blenderCore.FS.readFile('/gpu-output/result.json',{encoding:'utf8'})"))
        assert checks['version']==[5,2,2],checks
        assert checks['checks']=={'RGBA8':True,'RGBA16F':True,'RGBA32F':True,'packed_hdr':True,
                                 'R16F_storage':True,'RG16F_storage':True,
                                 'R16_storage':True,'RG16_storage':True,'RGBA16_storage':True,
                                 'switch_fallthrough':True,'volume_query':True,
                                 'atomic_image_coherence':True,'buffered_image_coherence':True,'float32_nearest_sampling':True,'float32_texel_load_helpers':True,'float32_texel_load':True,'shader_lifetime_cache':True,
                                 'array_layers':True,'cube_faces':True,'builtin_shader_triangle':True,
                                 'font_storage_shader':True,'depth_stencil_clear':True,
                                 'depth_pick_subrectangles':True},checks
        aspect_checks=page.evaluate('''async()=>{
          const device=nativeTestDevice,results=[];
          for(const texture of nativeDepthTargets){
            const expected={17:[90,0.75],19:[60,0.25],21:[123,0.5]}[texture.width];
            for(const [aspect,index,bytes] of [['stencil-only',0,1],['depth-only',1,4]]){
              device.pushErrorScope('validation');
              const buffer=device.createBuffer({size:256*13,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
              const encoder=device.createCommandEncoder();
              encoder.copyTextureToBuffer({texture,aspect},{buffer,bytesPerRow:256,rowsPerImage:13},[texture.width,13,1]);
              device.queue.submit([encoder.finish()]);await buffer.mapAsync(GPUMapMode.READ);
              const data=new DataView(buffer.getMappedRange());let valid=true;
              for(let y=0;y<13;y++)for(let x=0;x<texture.width;x++){
                const offset=y*256+x*bytes,value=bytes===1?data.getUint8(offset):data.getFloat32(offset,true);
                valid&&=value===expected[index];
              }
              buffer.unmap();buffer.destroy();
              const error=await device.popErrorScope();
              results.push({width:texture.width,aspect,valid,error:error?.message});
            }
          }
          return results;
        }''')
        assert len(aspect_checks)==6 and all(item['valid'] and not item.get('error') for item in aspect_checks),aspect_checks
        assert not errors,errors
        diagnostics.write(json.dumps(page.evaluate('({stdout:coreOutput,stderr:coreErrors})'),indent=2))
        diagnostics.close()
        browser.close()
    print('PASS: actual Blender GPU backend, textures, font pixels, builtin shaders, uniforms, vertex batches and synchronous framebuffer readback after network disconnect.')
finally:
    server.shutdown();server.server_close()
