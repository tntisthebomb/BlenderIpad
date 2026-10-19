#!/usr/bin/env python3
"""Verify actual editor pixels, input, native files, persistence and offline reload."""
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
        scale=float(os.environ.get('BLENDER_EDITOR_SCALE','1'))
        splash=os.environ.get('BLENDER_EDITOR_SPLASH')=='1'
        context=browser.new_context(viewport={'width':1024,'height':768},has_touch=True,
                                    device_scale_factor=scale)
        arguments=([] if splash else ['--factory-startup'])+['--offline-mode','--disable-autoexec','--threads','2',
                   '--python','/browser_startup.py','--python-expr',
                   ('BROWSER_TEST_SPLASH=True\n' if splash else '')+(ROOT/'tests/blender_editor_scene.py').read_text()]
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
            page.wait_for_function("document.body.dataset.started || document.body.dataset.error",timeout=300000)
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
            assert page.evaluate('crossOriginIsolated && !!navigator.serviceWorker.controller')
            page.wait_for_function("blenderEditor.FS.analyzePath('/editor-state.json').exists",timeout=120000)
            def state():
                return json.loads(page.evaluate("blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})"))
            initial=state()
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
            if splash:
                # Use the real first-run splash and dismiss it by touching the
                # viewport outside its block, as in the device crash report.
                page.touchscreen.tap(box['x']+box['width']*0.08,box['y']+box['height']*0.45)
                page.keyboard.press('Escape')
            page.mouse.move(box['x']+box['width']*0.4,box['y']+box['height']*0.5)
            page.locator('#canvas').focus()
            for key in ['g','x','1','Enter']: page.keyboard.press(key)
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).location[0]===1",timeout=30000)
            assert not state()['errors'],state()
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'deselect',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.length===0",timeout=30000)
            position=state()['object_position']
            assert position, state()
            scale=page.evaluate('devicePixelRatio')
            page.touchscreen.tap(box['x']+position[0]/scale,box['y']+box['height']-position[1]/scale)
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.includes('Cube')",timeout=30000)
            # Exercise another native popup and an actual box-select gesture;
            # a single Cube tap does not cover the failing picking paths.
            page.keyboard.press('F3')
            page.locator('#canvas').screenshot(path=str(ROOT/'.cache/blender-editor-search.png'))
            page.keyboard.press('Escape')
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'deselect',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.length===0")
            position=state()['object_position']
            center_x=box['x']+position[0]/scale
            center_y=box['y']+box['height']-position[1]/scale
            page.mouse.move(center_x,center_y)
            page.keyboard.press('b')
            touch=context.new_cdp_session(page)
            touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':center_x-24,'y':center_y-24}]})
            for step in range(1,6):
                touch.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':center_x-24+step*9.6,'y':center_y-24+step*9.6}]})
                page.wait_for_timeout(40)
            touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            touch.detach()
            page.wait_for_function("JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).selected.includes('Cube')",timeout=30000)
            assert not page.evaluate('window.editorErrors.length'),page.evaluate('window.editorErrors')
            assert not page.evaluate("editorOutput.filter(line=>/WGPU_SH.*FAIL|WGPU_SHADER translate FAILED|WGPU_BATCH skipped/.test(line))")
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
            page.wait_for_function("document.body.dataset.started || document.body.dataset.error",timeout=300000)
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
            assert page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/keyboard-scene.blend'))")==saved
            if splash:
                page.locator('#canvas').screenshot(path=str(ROOT/'.cache/blender-editor-offline-startup.png'))
                box=page.locator('#canvas').bounding_box()
                page.touchscreen.tap(box['x']+box['width']*0.08,box['y']+box['height']*0.45)
                page.keyboard.press('Escape')
            page.evaluate("blenderEditor.FS.writeFile('/editor-command.json',JSON.stringify({operation:'load',path:'/projects/keyboard-scene.blend'}))")
            page.wait_for_function("blenderEditor.FS.analyzePath('/editor-state.json').exists && JSON.parse(blenderEditor.FS.readFile('/editor-state.json',{encoding:'utf8'})).filepath==='/projects/keyboard-scene.blend'",timeout=60000)
            assert state()['location']==[1,0,0] and not state()['errors'],state()
            assert not errors,errors
        finally:
            try:
                (ROOT/'.cache/blender-editor-browser-log.json').write_text(json.dumps(page.evaluate('({output:window.editorOutput,errors:window.editorErrors})'),indent=2))
            except Exception: pass
            browser.close()
    print('PASS: actual Blender editor canvas, GHOST keyboard transform and touch selection, native project save/load, durable files and offline application reload.')
finally:
    server.shutdown();server.server_close()
