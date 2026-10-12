#!/usr/bin/env python3
"""Validate real WASM execution, keyboard transforms and offline reload in Chromium.
Set CHROMIUM_PATH when the system browser is installed outside /usr/lib/chromium.
"""
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with socket.socket() as port_socket:
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
server = subprocess.Popen(["python3", str(ROOT / "scripts/serve.py"), "--port", str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
url = f"http://127.0.0.1:{port}/"
try:
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                assert response.status == 200
            break
        except OSError:
            if server.poll() is not None:
                raise RuntimeError("Development server exited during startup")
            time.sleep(0.05)
    else:
        raise RuntimeError("Development server did not become ready")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH", "/usr/lib/chromium/chromium"),
            args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1180, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.get_by_text("5 source checks passed · Blender 5.2.2").wait_for()
        page.get_by_text("Downloaded · ready for offline reload").wait_for()
        assert page.evaluate("crossOriginIsolated") is True
        viewport = page.locator("#viewport")
        viewport.click()
        for key in ["g", "x", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
        assert page.locator('[data-field="location-0"]').inner_text() == "X 0.10"
        for key in ["r", "z", "ArrowRight", "Escape"]:
            page.keyboard.press(key)
        assert page.locator('[data-field="rotation-2"]').inner_text() == "Z 0.00°"
        for key in ["s", "y", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
        assert page.locator('[data-field="scale-1"]').inner_text() == "Y 1.10"
        assert page.locator('[data-field="location-0"]').inner_text() == "X 0.10"
        page.locator("#reset").click()
        assert page.locator('[data-field="location-0"]').inner_text() == "X 0.00"
        assert page.locator('[data-field="scale-1"]').inner_text() == "Y 1.00"
        (ROOT / "test-results").mkdir(exist_ok=True)
        page.screenshot(path=str(ROOT / "test-results/desktop.png"), full_page=True)
        context.set_offline(True)
        page.reload()
        page.get_by_text("5 source checks passed · Blender 5.2.2").wait_for()
        page.get_by_text("Downloaded · ready for offline reload").wait_for()
        assert page.evaluate("async () => (await fetch('./engine/source.tar.gz')).ok")
        viewport.click()
        for key in ["g", "z", "ArrowUp", "Enter"]:
            page.keyboard.press(key)
        assert page.locator('[data-field="location-2"]').inner_text() == "Z 0.10"
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(ROOT / "test-results/mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
        print("PASS: source math execution, keyboard move/scale/cancel/reset, isolated headers, offline reload, mobile layout.")
finally:
    server.terminate()
    server.wait(timeout=10)
