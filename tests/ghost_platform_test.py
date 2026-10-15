#!/usr/bin/env python3
"""Test native Blender GHOST events across a browser/WASM boundary, not JS imitation."""
import os
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT / ".cache/ghost-build")))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH", "/usr/lib/chromium/chromium"), args=["--no-sandbox"])
        context = browser.new_context(has_touch=True, viewport={"width": 1100, "height": 850})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{server.server_port}/ghost-platform.html")
        page.wait_for_function("document.body.dataset.ready === 'true'")
        snapshot = lambda: page.evaluate("nativeGhostSnapshot()")
        state = snapshot()
        assert state["backend"] == "WEB" and state["width"] == 800 and state["height"] == 450, state
        canvas = page.locator("#canvas")
        canvas.click()
        baseline = snapshot()
        page.keyboard.down("g")
        state = snapshot()
        assert state["keydown"] == baseline["keydown"] + 1, state
        assert state["key"] == page.evaluate("nativeGhost._ghost_probe_key_g()")
        assert page.evaluate("nativeGhost.ccall('ghost_probe_text','string',[],[])") == "g"
        page.keyboard.down("g")
        assert snapshot()["repeat"] == 1
        page.keyboard.up("g")
        assert snapshot()["keyup"] == baseline["keyup"] + 1

        page.keyboard.down("ShiftRight")
        assert snapshot()["right_shift"] == 1
        assert snapshot()["left_shift"] == 0
        box = canvas.bounding_box()
        page.mouse.move(box["x"] + 50, box["y"] + 50)
        assert snapshot()["left_shift"] == 0, snapshot()
        # Blur must synthesize release events instead of leaving a stuck modifier.
        page.locator("#outside").focus()
        assert snapshot()["right_shift"] == 0
        page.keyboard.up("ShiftRight")
        page.keyboard.press("a")
        assert snapshot()["keydown"] == baseline["keydown"] + 3

        canvas.focus()
        page.evaluate("document.getElementById('canvas').dispatchEvent(new KeyboardEvent('keydown',{code:'KeyE',key:'é',bubbles:true}))")
        snapshot()
        assert page.evaluate("nativeGhost.ccall('ghost_probe_text','string',[],[])") == "é"
        page.evaluate("document.getElementById('canvas').dispatchEvent(new KeyboardEvent('keyup',{code:'KeyE',key:'é',bubbles:true}))")
        before = snapshot()
        page.mouse.move(box["x"] + 100, box["y"] + 100)
        page.mouse.wheel(0, 120)
        page.wait_for_function("nativeGhostSnapshot().wheel > " + str(before["wheel"]))
        before = snapshot()
        page.mouse.down()
        assert snapshot()["left_button"] == 1
        page.mouse.move(1050, 800)
        page.mouse.up()
        assert snapshot()["left_button"] == 0
        assert snapshot()["mouseup"] == before["mouseup"] + 1

        before = snapshot()
        canvas.tap()
        after = snapshot()
        assert after["mousedown"] == before["mousedown"] + 1, (before, after)
        assert after["mouseup"] == before["mouseup"] + 1, (before, after)
        assert after["left_button"] == 0
        # Deliver actual browser multi-touch events through the compiled native
        # backend and inspect Blender's event queue, including click release.
        touch_session=context.new_cdp_session(page)
        def touches(kind,span=35,offset=0,count=2):
            points=[] if kind=='touchEnd' else [
                {'id':1,'x':box['x']+200-span+offset,'y':box['y']+150},
                {'id':2,'x':box['x']+200+span+offset,'y':box['y']+150}]
            points=points[:count]
            touch_session.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':points})
        before=snapshot()
        touches('touchStart',count=1)
        assert snapshot()['left_button']==1
        touches('touchStart')
        assert snapshot()['left_button']==0
        touches('touchMove',offset=20)
        touches('touchEnd')
        after=snapshot()
        assert after['trackpad_pan']>before['trackpad_pan'],(before,after)
        assert after['pan_x']-before['pan_x']==20,(before,after)
        assert after['mousedown']==before['mousedown']+1,(before,after)
        assert after['mouseup']==before['mouseup']+1,(before,after)
        assert after['left_button']==0,after
        before=snapshot()
        touches('touchStart',span=35)
        touches('touchMove',span=70)
        touches('touchEnd')
        after=snapshot()
        assert after['trackpad_zoom']>before['trackpad_zoom'],(before,after)
        assert 85<=after['zoom_x']-before['zoom_x']<=88,(before,after)
        assert after['left_button']==0,after
        before=snapshot()
        canvas.tap()
        after=snapshot()
        assert after['mousedown']==before['mousedown']+1,(before,after)
        assert after['mouseup']==before['mouseup']+1 and after['left_button']==0,(before,after)
        touches('touchStart')
        touch_session.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})
        assert snapshot()['left_button']==0
        before=snapshot()
        canvas.tap()
        after=snapshot()
        assert after['mousedown']==before['mousedown']+1,(before,after)
        assert after['mouseup']==before['mouseup']+1 and after['left_button']==0,(before,after)
        page.evaluate("const c=document.getElementById('canvas');c.style.width='640px';c.style.height='360px';dispatchEvent(new Event('resize'))")
        assert snapshot()["width"] == 640 and snapshot()["height"] == 360
        before = snapshot()
        page.evaluate("nativeGhost._ghost_probe_redraw()")
        assert snapshot()["redraws"] == before["redraws"] + 1

        page.evaluate("nativeGhost._ghost_probe_close_window()")
        canvas.click()
        assert page.evaluate("nativeGhost._ghost_probe_reopen_window()") == 1
        for _ in range(3):
            page.evaluate("nativeGhost._ghost_probe_shutdown()")
            canvas.click()  # No dangling native callbacks after disposal.
            assert page.evaluate("nativeGhost._ghost_probe_init()") == 1
            assert snapshot()["backend"] == "WEB"
        assert not errors, errors
        browser.close()
    print("PASS: actual GHOST factory/window/event queue; keyboard, repeat, UTF-8, modifiers, blur, mouse, touch, wheel, resize, redraw and lifecycle.")
finally:
    server.shutdown()
    server.server_close()
