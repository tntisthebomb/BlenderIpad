#!/usr/bin/env python3
"""Execute actual Blender GPU resources and drawing through its own Python API."""
import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--engine',choices=('BLENDER_WORKBENCH','BLENDER_EEVEE','CYCLES'),default='BLENDER_WORKBENCH')
options=parser.parse_args()
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
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        diagnostics=(ROOT/'.cache'/('blender-render-'+options.engine+'-console.log')).open('w')
        page.on('console',lambda message: (diagnostics.write(message.type+': '+message.text+'\n'), diagnostics.flush()))
        debug_session=context.new_cdp_session(page)
        debug_session.send('Inspector.enable')
        debug_session.on('Inspector.targetCrashed',lambda event: (diagnostics.write('target-crash: '+json.dumps(event)+'\n'), diagnostics.flush()))
        page.goto(f'http://127.0.0.1:{server.server_port}/core.html')
        page.wait_for_function('document.body.dataset.ready || document.body.dataset.error',timeout=300000)
        assert page.locator('body').get_attribute('data-ready')=='true',page.locator('body').get_attribute('data-error')
        assert page.evaluate('crossOriginIsolated')
        page.evaluate('source=>blenderCore.FS.writeFile("/gpu_test.py",source)',(ROOT/'tests/blender_render_scene.py').read_text())
        context.set_offline(True)
        page.evaluate("engine=>blenderCore.runBlenderMain(['--background','--factory-startup','--offline-mode','--disable-autoexec','--threads','2','--python-exit-code','1','--python','/gpu_test.py','--',engine])",options.engine)
        page.wait_for_function('coreExit !== null || document.body.dataset.error',timeout=300000)
        assert page.evaluate('coreExit')==0,page.evaluate('coreErrors')
        checks=json.loads(page.evaluate("blenderCore.FS.readFile('/render-output/result.json',{encoding:'utf8'})"))
        assert checks['version']==[5,2,2],checks
        assert checks['engine']==options.engine,checks
        assert set(checks['checks'])=={'red','green','empty'},checks
        from PIL import Image
        import io
        for label in ('red','green','empty'):
            data=bytes(page.evaluate("path=>Array.from(blenderCore.FS.readFile(path))",'/render-output/'+label+'.png'))
            picture=Image.open(io.BytesIO(data)).convert('RGBA')
            assert picture.size==(64,64),picture.size
            assert picture.getextrema()[3][1]==(0 if label=='empty' else 255)
            (ROOT/'.cache'/('blender-render-'+options.engine+'-'+label+'.png')).write_bytes(data)
        diagnostics.write(json.dumps(checks)+'\n')
        assert not errors,errors
        diagnostics.write(json.dumps(page.evaluate('({stdout:coreOutput,stderr:coreErrors})'),indent=2))
        diagnostics.close()
        browser.close()
    print('PASS: actual native scene rendering and PNG pixels after network disconnect.')
finally:
    server.shutdown();server.server_close()
