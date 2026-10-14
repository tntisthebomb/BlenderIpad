"""Browser transfer UI fixtures; these bytes are not Blender engine acceptance."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
with TemporaryDirectory(dir=ROOT/'.cache') as directory:
    base=Path(directory)
    markup=(ROOT/'native/browser/blender_editor.html').read_text().split('<script src="blender-core.js">')[0]
    # An explicitly limited in-memory filesystem exposes transfer failures. Real
    # IDBFS/native files are independently checked by editor browser acceptance.
    fixture='''<script>
    const files=new Map(),directories=new Set(['/','/projects']);
    const clean=path=>path.replace(/\\/+/g,'/').replace(/\\/$/,'');
    window.failStorage=false; window.failWrite=false;
    window.blenderEditor={FS:{
      syncfs:(populate,callback)=>setTimeout(()=>callback(failStorage ? new Error('Quota exceeded') : null),0),
      mkdirTree:path=>{const parts=clean(path).split('/');let current='';for(const part of parts.slice(1)){current+='/'+part;directories.add(current)}},
      analyzePath:path=>({exists:files.has(clean(path))||directories.has(clean(path))}),
      writeFile:(path,bytes)=>{if(failWrite && path.endsWith('bad.png')) throw new Error('Write failed');files.set(clean(path),new Uint8Array(bytes));},
      readFile:path=>files.get(clean(path)),unlink:path=>files.delete(clean(path)),
      stat:path=>({mode:directories.has(clean(path)) ? 1 : 0}),isDir:mode=>mode===1,
      readdir:path=>{const parent=clean(path)+'/';return ['.','..',...new Set([...files.keys(),...directories].filter(p=>p.startsWith(parent)&&p!==parent).map(p=>p.slice(parent.length).split('/')[0]))]}
    }};
    document.getElementById('status').hidden=true;
    </script><script src="editor_files.js"></script></body></html>'''
    (base/'index.html').write_text(markup+fixture)
    (base/'editor_files.js').write_bytes((ROOT/'native/browser/editor_files.js').read_bytes())
    folder=base/'linked-project'
    (folder/'textures').mkdir(parents=True)
    (folder/'scene.blend').write_bytes(b'Project fixture')
    (folder/'textures/albedo.png').write_bytes(b'Texture fixture')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
            try:
                page=browser.new_page(accept_downloads=True)
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.locator('#import-folder').set_input_files(str(folder))
                page.wait_for_function("document.getElementById('file-message').textContent.startsWith('Imported')")
                assert page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/linked-project/textures/albedo.png'))")==list(b'Texture fixture')
                page.locator('#import-folder').set_input_files(str(folder))
                page.wait_for_function("document.getElementById('file-message').textContent.startsWith('Import failed')")
                assert page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/linked-project/scene.blend'))")==list(b'Project fixture')
                page.evaluate('failStorage=true')
                page.locator('#export-files').click()
                page.locator('#saved-files').select_option('/projects/linked-project/scene.blend')
                with page.expect_download() as pending: page.locator('#download-file').click()
                download=pending.value
                assert download.suggested_filename=='scene.blend'
                assert Path(download.path()).read_bytes()==b'Project fixture'
                assert 'Browser storage failed' in page.locator('#file-message').inner_text()
                page.evaluate('failStorage=false;failWrite=true')
                page.locator('#import-files').set_input_files([
                    {'name':'good.png','mimeType':'image/png','buffer':b'good'},
                    {'name':'bad.png','mimeType':'image/png','buffer':b'bad'}])
                page.wait_for_function("document.getElementById('file-message').textContent.startsWith('Import failed')")
                assert not page.evaluate("blenderEditor.FS.analyzePath('/projects/good.png').exists")
                assert page.evaluate("blenderEditor.FS.analyzePath('/projects/linked-project/scene.blend').exists")
            finally: browser.close()
    finally: server.shutdown();server.server_close()
print('PASS: linked import paths, conflict preservation, partial-import rollback and backup download despite storage failure (transfer fixtures only).')
