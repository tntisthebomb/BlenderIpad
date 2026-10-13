#!/usr/bin/env python3
"""Run application acceptance and record the exact tested browser assets."""
import hashlib
import json
from pathlib import Path
import subprocess
from setup_browser import CACHE, ROOT

ASSETS = ('index.html', 'editor.html', 'editor_files.js', 'blender-core.js',
          'blender-core.wasm', 'blender-core.data', 'manifest.webmanifest',
          'icon.svg', 'service-worker.js')
TESTS = ('tests/blender_gpu_browser_test.py', 'tests/blender_gpu_scene.py',
         'tests/blender_editor_browser_test.py', 'tests/blender_editor_scene.py')

def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()

def snapshot():
    directory = CACHE / 'blender-webgpu-browser'
    return {'assets': {name: digest(directory / name) for name in ASSETS},
            'tests': {name: digest(ROOT / name) for name in TESTS}}

if __name__ == '__main__':
    stamp = CACHE / 'blender-webgpu-browser/editor-validation.json'
    stamp.unlink(missing_ok=True)
    before = snapshot()
    interpreter = CACHE / 'browser-tests/bin/python'
    for script in ('tests/blender_gpu_browser_test.py', 'tests/blender_editor_browser_test.py'):
        subprocess.run([str(interpreter), str(ROOT / script)], cwd=ROOT, check=True)
    if snapshot() != before:
        raise SystemExit('Assets or acceptance fixtures changed during validation.')
    stamp.write_text(json.dumps({'version': [5, 2, 2], 'profile': 'experimental-editor',
        'checks': ['gpu_resources', 'font_pixels', 'native_viewport', 'keyboard_transform',
                   'touch_selection', 'native_save_load', 'durable_projects', 'offline_reload'],
        **before}, indent=2) + '\n')
    print('PASS: editor acceptance recorded for the exact browser assets and fixtures.')
