#!/usr/bin/env python3
"""Verify actual editor pixels, input, native files, persistence and offline reload."""
import argparse
import json
import os
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--tablet',action='store_true')
options=parser.parse_args()
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
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
        context=browser.new_context(viewport={'width':1024,'height':768},has_touch=True,
            device_scale_factor=float(os.environ.get('EDITOR_DEVICE_SCALE','2')))
        if options.tablet:
            context.add_init_script('''
              Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});
              Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});
              const request=GPUAdapter.prototype.requestDevice;
              GPUAdapter.prototype.requestDevice=function(options={}){
                return request.call(this,{...options,requiredFeatures:
                  (options.requiredFeatures||[]).filter(f=>f!=='float32-filterable')});
              };
            ''')
        context.add_init_script('''
            const requestAdapter=navigator.gpu.requestAdapter.bind(navigator.gpu);
            navigator.gpu.requestAdapter=async(...args)=>{
                const adapter=await requestAdapter(...args);
                if(adapter){const requestDevice=adapter.requestDevice.bind(adapter);
                    adapter.requestDevice=async(...args)=>window.testDevice=await requestDevice(...args);}
                return adapter;
            };
        ''')
        arguments=['--factory-startup','--offline-mode','--disable-autoexec','--threads',('1' if options.tablet else '2'),
                   '--python','/browser_startup.py','--python-expr',
                   (ROOT/'tests/blender_editor_scene.py').read_text()]
        context.add_init_script('window.editorArguments='+json.dumps(arguments)+';')
        page=context.new_page()
        # Cold native shader compilation can block the browser main thread for
        # over 30 seconds before the first frame. Keep explicit readiness and
        # output assertions, with enough time for selector requests to execute.
        page.set_default_timeout(180000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            if options.tablet:page.locator('#start-editor').click()
            page.wait_for_function("document.body.dataset.started || document.body.dataset.error",timeout=300000)
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
            page.wait_for_function("document.body.dataset.rendered==='true' || document.body.dataset.error",timeout=300000)
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
            assert page.evaluate('crossOriginIsolated && !!navigator.serviceWorker.controller')
            page.wait_for_function("blenderEditor.FS.analyzePath('/editor-state.json').exists",timeout=120000)
            def state():
                return json.loads(page.evaluate("blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})"))
            initial=state()
            if options.tablet:
                region=initial['view']['region']
                backing=page.evaluate('[canvas.width,canvas.height]')
                assert region[0]+region[2]<=backing[0]+2 and region[1]+region[3]<=backing[1]+2,(region,backing)
            assert initial['version']==[5,2,2] and initial['backend']=='WEBGPU',initial
            assert initial['windows']==1 and 'VIEW_3D' in initial['areas'],initial
            assert initial['active']=='Cube' and not initial['errors'],initial
            screenshot=ROOT/'.cache/blender-editor-frame.png'
            # The native state timer can run before shader compilation and the
            # first submitted canvas frame complete. Wait for actual pixels;
            # keep the visible-output assertion and graphics errors as failures.
            deadline=time.monotonic()+120
            while True:
                assert not page.evaluate('window.editorErrors.length'),page.evaluate('window.editorErrors')
                page.locator('#canvas').screenshot(path=str(screenshot))
                picture=Image.open(screenshot).convert('RGB')
                if len(picture.getcolors(picture.width*picture.height))>64: break
                if time.monotonic()>=deadline: break
                page.wait_for_timeout(250)
            assert len(picture.getcolors(picture.width*picture.height))>64,'Editor presentation is blank or incomplete'
            shader_failures=page.evaluate("editorOutput.filter(line=>/WGPU_SH.*FAIL|WGPU_SHADER translate FAILED|WGPU_BATCH skipped/.test(line))")
            assert not shader_failures,shader_failures
            # Focus the actual 3D editor area, then use real GHOST keyboard events.
            box=page.locator('#canvas').bounding_box()
            page.mouse.move(box['x']+box['width']*0.4,box['y']+box['height']*0.5)
            page.locator('#canvas').focus()
            for key in ['g','x','1','Enter']: page.keyboard.press(key)
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).location[0]===1",timeout=30000)
            assert not state()['errors'],state()
            # The on-screen bridge preserves Blender's active native text field.
            def keyboard_text(text, composing=False):
                page.evaluate('''({text,composing})=>{
                  const input=document.getElementById('tablet-text');
                  if(composing) input.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));
                  input.value='\ufeff'+text;
                  input.dispatchEvent(new InputEvent('input',{inputType:composing?'insertCompositionText':'insertText',
                    data:text,isComposing:composing,bubbles:true}));
                  if(composing) {
                    input.dispatchEvent(new CompositionEvent('compositionend',{data:text,bubbles:true}));
                    input.dispatchEvent(new InputEvent('input',{inputType:'insertText',data:text,bubbles:true}));
                  }
                }''',{'text':text,'composing':composing})
            def wait_name(name):
                page.wait_for_function("name=>JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).active===name",arg=name,timeout=30000)
            page.keyboard.press('F2')
            page.locator('#tablet-keyboard').click()
            keyboard_text('TabletCube')
            page.locator('#tablet-keys button').filter(has_text='Enter').click()
            wait_name('TabletCube')
            page.locator('#tablet-keys button').filter(has_text='Done').click()
            page.keyboard.press('F2')
            page.locator('#tablet-keyboard').click()
            # Ctrl+A is forwarded to Blender, rather than selecting the sentinel.
            page.locator('#tablet-text').press('Control+a')
            keyboard_text('CubeΩ',composing=True)
            page.locator('#tablet-keys button').filter(has_text='Enter').click()
            wait_name('CubeΩ')
            page.locator('#tablet-keys button').filter(has_text='Done').click()
            page.keyboard.press('F2')
            page.locator('#tablet-keyboard').click()
            page.locator('#tablet-keys').get_by_role('button',name='→',exact=True).click()
            page.locator('#tablet-keys').get_by_role('button',name='⌫',exact=True).click()
            page.locator('#tablet-keys button').filter(has_text='Enter').click()
            wait_name('Cube')
            page.locator('#tablet-keys button').filter(has_text='Done').click()
            # Real multi-touch events must change the native viewport, rather
            # than moving the selected mesh or leaving a selection drag held.
            native_view=state()['view']
            region=native_view['region']
            scale=page.evaluate('canvas.width/canvas.clientWidth')
            cx=box['x']+(region[0]+region[2]*0.5)/scale
            cy=box['y']+box['height']-(region[1]+region[3]*0.5)/scale
            touch_session=context.new_cdp_session(page)
            def two_fingers(kind,half_span,offset=0):
                points=[] if kind=='touchEnd' else [
                    {'id':1,'x':cx-half_span+offset,'y':cy},
                    {'id':2,'x':cx+half_span+offset,'y':cy}]
                touch_session.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':points})
            two_fingers('touchStart',40)
            two_fingers('touchMove',40,35)
            two_fingers('touchEnd',40)
            page.wait_for_function('rotation=>{const v=JSON.parse(blenderEditor.FS.readFile("/editor-state.json",{encoding:"utf8"})).view;return v && v.rotation.some((x,i)=>Math.abs(x-rotation[i])>0.001)}',arg=native_view['rotation'],timeout=30000)
            distance=state()['view']['distance']
            two_fingers('touchStart',35)
            two_fingers('touchMove',65)
            two_fingers('touchEnd',65)
            page.wait_for_function('distance=>Math.abs(JSON.parse(blenderEditor.FS.readFile("/editor-state.json",{encoding:"utf8"})).view.distance-distance)>distance*0.01',arg=distance,timeout=30000)
            assert state()['location']==[1,0,0],state()
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'deselect',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.length===0",timeout=30000)
            position=state()['object_position']
            assert position, state()
            scale=page.evaluate('canvas.width/canvas.clientWidth')
            page.touchscreen.tap(box['x']+position[0]/scale,box['y']+box['height']-position[1]/scale)
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.includes('Cube')",timeout=30000)
            # The native application writes this project, rather than JS fabricating bytes.
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'save',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("blenderEditor.FS.analyzePath('/projects/keyboard-scene.blend').exists",timeout=30000)
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).last_operation==='save'",timeout=30000)
            assert not state()['errors'],state()
            page.evaluate("new Promise((resolve,reject)=>blenderEditor.FS.syncfs(false,error=>error ? reject(error) : resolve()))")
            saved=page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/keyboard-scene.blend'))")
            # Blender supports both ordinary and Zstandard-compressed projects.
            assert bytes(saved[:7])==b'BLENDER' or bytes(saved[:4])==b'\x28\xb5\x2f\xfd',saved[:16]
            # A new runtime must boot from the installed cache with the server offline.
            context.set_offline(True)
            page.reload()
            if options.tablet:page.locator('#start-editor').click()
            page.wait_for_function("document.body.dataset.started || document.body.dataset.error",timeout=300000)
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
            assert page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/keyboard-scene.blend'))")==saved
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'load',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("blenderEditor.FS.analyzePath('/editor-state.json').exists && JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).filepath==='/projects/keyboard-scene.blend'",timeout=60000)
            assert state()['location']==[1,0,0] and not state()['errors'],state()
            # Suspension releases input, stops drawing, and resumes the same
            # scene; orientation changes must preserve a working native editor.
            page.keyboard.down('Shift')
            page.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
            page.wait_for_timeout(300)
            suspended=state()['observations']
            page.wait_for_timeout(500)
            assert state()['observations']==suspended,'Native main loop kept running while hidden'
            page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
            page.wait_for_function("count=>JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).observations>count",arg=suspended,timeout=30000)
            page.keyboard.up('Shift')
            page.set_viewport_size({'width':768,'height':1024})
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).location[0]===1")
            assert not state()['errors'],state()
            if options.tablet:
                # Portrait now renders below CSS resolution. Native region
                # bounds and touch selection must follow the backing scale.
                page.wait_for_function('canvas.clientHeight>canvas.clientWidth && canvas.height===800 && canvas.width<canvas.clientWidth',timeout=30000)
                page.wait_for_function("""()=>{const r=JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).view.region;
                  return r[0]+r[2]<=canvas.width+2 && r[1]+r[3]<=canvas.height+2;}""",timeout=30000)
                page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'deselect',path:'/projects/keyboard-scene.blend'}))")
                page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.length===0")
                portrait=page.locator('#canvas').bounding_box()
                position=state()['object_position']
                scale=page.evaluate('canvas.width/canvas.clientWidth')
                page.touchscreen.tap(portrait['x']+position[0]/scale,portrait['y']+portrait['height']-position[1]/scale)
                page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.includes('Cube')")
            # Native memory/files remain accessible after a real GPU device
            # loss. Export must still return the exact project bytes.
            page.evaluate('testDevice.destroy()')
            page.wait_for_function("document.body.dataset.error?.startsWith('Graphics device lost')")
            page.locator('#recover-files').click()
            page.locator('#saved-files').select_option('/projects/keyboard-scene.blend')
            with page.expect_download() as pending:
                page.locator('#download-file').click()
            assert Path(pending.value.path()).read_bytes()==bytes(saved)
            assert not errors,errors
            # Simulate an unavailable adapter on the next boot. Recovery reads
            # the real IDBFS records without instantiating the native engine.
            context.add_init_script('navigator.gpu.requestAdapter=async()=>null;')
            page.reload()
            if options.tablet:page.locator('#start-editor').click()
            page.wait_for_function("document.body.dataset.error?.includes('No WebGPU graphics adapter')")
            assert not page.evaluate('!!window.blenderEditor')
            page.locator('#recover-files').click()
            page.locator('#saved-files').select_option('/projects/keyboard-scene.blend')
            with page.expect_download() as pending:
                page.locator('#download-file').click()
            assert Path(pending.value.path()).read_bytes()==bytes(saved)
        finally:
            try:
                (ROOT/'.cache/blender-editor-browser-log.json').write_text(json.dumps(page.evaluate('({output:window.editorOutput,errors:window.editorErrors})'),indent=2))
            except Exception: pass
            browser.close()
    print('PASS: native editor, high-density input, native project persistence/offline reload, suspension/orientation and exact backup after GPU device loss.')
finally:
    server.shutdown();server.server_close()
