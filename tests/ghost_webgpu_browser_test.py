#!/usr/bin/env python3
"""Validate actual GHOST WebGPU frame ownership, pixels, resize and recreation."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'.cache/ghost-webgpu-build')))
Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as playwright:
        executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
        environment=dict(os.environ)
        icd=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
        if icd.exists(): environment['VK_ICD_FILENAMES']=str(icd)
        browser=playwright.chromium.launch(executable_path=executable,env=environment,args=[
            '--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=browser.new_page()
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/ghost-webgpu.html')
        page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
        assert page.locator('body').get_attribute('data-ready')=='true',page.locator('body').get_attribute('data-error')
        page.wait_for_function('window.ghostGPU')
        def frame(number, alternate):
            assert page.evaluate('alternate => new Promise(resolve => requestAnimationFrame(() => resolve(ghostGPU._ghost_gpu_frame(alternate))))',alternate)==1
            page.wait_for_function(f"Number(document.body.dataset.frames)>={number} || document.body.dataset.error")
            assert not page.locator('body').get_attribute('data-error'),page.locator('body').get_attribute('data-error')
        frame(1,0)
        frame(2,1)
        page.evaluate('''() => {
            const canvas=document.getElementById('canvas');
            canvas.width=96; canvas.height=72;
            canvas.style.width='96px'; canvas.style.height='72px';
            window.dispatchEvent(new Event('resize'));
        }''')
        frame(3,0)
        assert page.evaluate('ghostGPU._ghost_gpu_close()')==1
        assert page.evaluate('ghostGPU._ghost_gpu_frame(0)')==0
        assert page.evaluate('ghostGPU._ghost_gpu_reopen()')==1
        frame(4,1)
        page.evaluate('''() => {
          window.drawing=true;
          function draw() {
            if (!window.drawing) return;
            if (!ghostGPU._ghost_gpu_frame(1)) document.body.dataset.error='continuous frame failed';
            requestAnimationFrame(draw);
          }
          requestAnimationFrame(draw);
        }''')
        page.wait_for_function('Number(document.body.dataset.frames)>=6 || document.body.dataset.error')
        screenshot=ROOT/'.cache/ghost-webgpu-frame.png'
        page.locator('#canvas').screenshot(path=str(screenshot))
        picture=Image.open(screenshot).convert('RGB')
        pixel=picture.getpixel((picture.width//2,picture.height//2))
        assert all(abs(actual-expected)<=1 for actual,expected in zip(pixel,(191,64,32))), ('Canvas presentation is blank or incorrect',pixel)
        page.evaluate('window.drawing=false')
        page.wait_for_function('ghostGPU._ghost_gpu_pending()===0')
        assert page.evaluate('ghostGPU._ghost_gpu_close()')==1
        assert page.evaluate('ghostGPU._ghost_gpu_shutdown()')==1
        assert not errors,errors
        browser.close()
    print('PASS: real GHOST WebGPU device-gated window, acquire/submit/release, pixel readback, visible canvas screenshot, resize, window recreation and shutdown.')
finally:
    server.shutdown();server.server_close()
