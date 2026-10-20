"""Late frame/rejected-wait failures must leave a report and project recovery UI."""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


with TemporaryDirectory(dir=ROOT / '.cache') as directory:
    base = Path(directory)
    # Run the production failure/report handlers without booting a native engine.
    markup = (ROOT / 'native/browser/blender_editor.html').read_text().split('(async()=>{')[0]
    markup += '''
window.pauseCount=0;window.destroyCount=0;
window.blenderEditor={pauseBlenderLoop(){pauseCount++},getBlenderMemoryBytes(){return 1024}};
graphicsDevice={destroy(){destroyCount++}};
document.body.dataset.started='true';status.hidden=true;
log('Last native operation: viewport picking');
</script><script src="editor_files.js"></script></body></html>'''
    (base / 'index.html').write_text(markup)
    for name in ('editor_files.js', 'startup_stats.js'):
        (base / name).write_bytes((ROOT / 'native/browser' / name).read_bytes())
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium'),
                args=['--no-sandbox'])
            try:
                page = browser.new_page(accept_downloads=True)
                for trigger in (
                    "setTimeout(()=>{throw new Error('Late frame picking failure')},0)",
                    "void Promise.reject(new Error('Late GPU wait failure'))",
                ):
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    assert page.evaluate('document.body.dataset.started') == 'true'
                    page.evaluate(trigger)
                    page.wait_for_function('!!document.body.dataset.error')
                    assert 'Late ' in page.locator('#status-message').inner_text()
                    assert page.locator('#recover-files').is_visible()
                    assert page.evaluate('[pauseCount,destroyCount]') == [1, 1]
                    # Later errors must not obscure the original exception.
                    first = page.evaluate('document.body.dataset.error')
                    page.evaluate("dispatchEvent(new ErrorEvent('error',{message:'Secondary failure'}))")
                    assert page.evaluate('document.body.dataset.error') == first
                    with page.expect_download() as pending:
                        page.locator('#error-device-report').click()
                    report = json.loads(Path(pending.value.path()).read_text())
                    assert report['error'] == first
                    assert report['runtimeErrors'] == [first]
                    assert report['recentOutput'][-1] == 'Last native operation: viewport picking'
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

print('PASS: real late frame/rejection errors stop the loop once and retain recovery and diagnostic reports.')
