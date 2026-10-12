#!/usr/bin/env python3
"""Touch buttons, viewport selection suppression, drag and pointer cancellation."""
import os
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT / "web")))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH", "/usr/lib/chromium/chromium"), args=["--no-sandbox"])
        context = browser.new_context(has_touch=True, viewport={"width": 1180, "height": 950})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.get_by_text("5 source checks passed · Blender 5.2.2").wait_for()
        assert page.get_by_role("button", name="Confirm", exact=True).is_disabled()
        page.get_by_role("button", name="Move", exact=True).tap()
        page.get_by_role("button", name="Y axis", exact=True).tap()
        page.get_by_role("button", name="Increase transform").tap()
        assert page.locator('[data-field="location-1"]').inner_text() == "Y 0.10"
        page.get_by_role("button", name="Cancel", exact=True).tap()
        assert page.locator('[data-field="location-1"]').inner_text() == "Y 0.00"
        page.get_by_role("button", name="Rotate", exact=True).tap()
        page.get_by_role("button", name="Z axis", exact=True).tap()
        page.get_by_role("button", name="Increase transform").tap()
        page.get_by_role("button", name="Confirm", exact=True).tap()
        assert page.locator('[data-field="rotation-2"]').inner_text() == "Z 5.00°"
        page.get_by_role("button", name="Scale", exact=True).tap()
        page.get_by_role("button", name="X axis", exact=True).tap()
        page.get_by_role("button", name="Decrease transform").tap()
        page.get_by_role("button", name="Confirm", exact=True).tap()
        assert page.locator('[data-field="scale-0"]').inner_text() == "X 0.90"

        page.get_by_role("button", name="Reset transform").tap()
        assert page.locator("#viewport").evaluate("e => getComputedStyle(e).userSelect") == "none"
        assert page.locator("#viewport").evaluate("e => getComputedStyle(e).touchAction") == "none"
        session = context.new_cdp_session(page)
        box = page.locator("#canvas").bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        def touch(kind, offset=0):
            session.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if kind in ["touchEnd", "touchCancel"] else [{"x": x + offset, "y": y}]})
        touch("touchStart")
        touch("touchMove", 70)
        touch("touchEnd")
        assert page.locator('[data-field="location-0"]').inner_text() != "X 0.00"
        assert page.get_by_role("button", name="Confirm", exact=True).is_disabled()
        assert page.evaluate("getSelection().toString()") == ""

        page.get_by_role("button", name="Reset transform").tap()
        touch("touchStart")
        touch("touchMove", 70)
        touch("touchCancel")
        expect(page.locator('[data-field="location-0"]')).to_have_text("X 0.00")
        # Touch controls hand focus back to the keyboard viewport.
        page.get_by_role("button", name="Move", exact=True).tap()
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Enter")
        assert page.locator('[data-field="location-0"]').inner_text() == "X 0.10"

        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        for button in page.locator('[data-command]').all():
            size = button.bounding_box()
            assert size["width"] >= 44 and size["height"] >= 44
        assert not errors, errors
        browser.close()
    print("PASS: touch move/rotate/scale, axis selection, confirm/cancel, drag, interruption recovery, keyboard handoff and 44px targets.")
finally:
    server.shutdown()
    server.server_close()
