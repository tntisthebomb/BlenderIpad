#!/usr/bin/env python3
"""Run application acceptance and record the exact tested browser assets."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
from setup_browser import CACHE, ROOT

ASSETS = ('index.html', 'editor.html', 'editor_files.js', 'blender-core.js',
          'blender-core.wasm', 'blender-core.data', 'manifest.webmanifest',
          'icon.svg', 'icon-192.png', 'icon-512.png', 'service-worker.js')
TESTS = ('tests/blender_gpu_browser_test.py', 'tests/blender_gpu_scene.py',
         'tests/blender_editor_browser_test.py', 'tests/blender_editor_scene.py',
         'tests/blender_render_browser_test.py', 'tests/blender_render_scene.py',
         'tests/offline_shell_browser_test.py', 'tests/editor_files_browser_test.py',
         'tests/blender_modeling_browser_test.py', 'tests/blender_modeling_scene.py',
         'tests/editor_install_failure_test.py',
         'tests/shader_semantics_browser_test.py', 'tests/shader_switch_fallthrough.comp',
         'tests/shader_switch_phi.comp', 'tests/shader_volume_query.comp',
         'tests/shader_atomic_image.comp', 'tests/shader_readwrite_texture.comp',
         'tests/shader_zbin_range.comp',
         'scripts/test_browser_lifecycle.py', 'tests/browser_lifecycle_probe.cc')

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
    parser = argparse.ArgumentParser()
    parser.add_argument('--eevee', action='store_true')
    parser.add_argument('--cycles', action='store_true')
    options = parser.parse_args()
    engines = ['BLENDER_WORKBENCH']
    if options.eevee:
        engines.append('BLENDER_EEVEE')
    if options.cycles:
        engines.append('CYCLES')
    stamp = CACHE / 'blender-webgpu-browser/editor-validation.json'
    failure_stamp = stamp.with_name('editor-failures.json')
    stamp.unlink(missing_ok=True)
    failure_stamp.unlink(missing_ok=True)
    before = snapshot()
    interpreter = CACHE / 'browser-tests/bin/python'
    failures = []
    def check(label, script, *arguments):
        result = subprocess.run([str(interpreter), str(ROOT / script), *arguments], cwd=ROOT)
        if result.returncode:
            failures.append({'check': label, 'exit_code': result.returncode})
    check('gpu_resources', 'tests/blender_gpu_browser_test.py')
    for engine in engines:
        check(engine, 'tests/blender_render_browser_test.py', '--engine', engine)
    for script in (
                   'tests/blender_modeling_browser_test.py', 'tests/blender_editor_browser_test.py', 'tests/offline_shell_browser_test.py',
                   'tests/editor_files_browser_test.py', 'tests/editor_install_failure_test.py'):
        check(script, script)
    if snapshot() != before:
        raise SystemExit('Assets or acceptance fixtures changed during validation.')
    if failures:
        failure_stamp.write_text(json.dumps({'failures': failures, **before}, indent=2) + '\n')
        raise SystemExit('Editor acceptance failed: ' + ', '.join(item['check'] for item in failures))
    stamp.write_text(json.dumps({'version': [5, 2, 2], 'profile': 'experimental-editor',
        'render_engines': engines,
        'checks': ['gpu_resources', 'font_pixels', 'native_viewport', 'keyboard_transform',
                   'touch_selection', 'native_save_load', 'durable_projects', 'offline_reload',
                   'workbench_render_png', 'suspension_orientation', 'device_loss_backup',
                   'atomic_updates', 'linked_asset_import', 'storage_failure_backup',
                   'modeling_geometry_nodes', 'armature_deformation', 'obj_interchange',
                   'embedded_python_threads',
                   'subdivision_surface',
                   'shader_switch_fallthrough', 'volume_texture_queries',
                   'atomic_image_coherence',
                   'adapter_unavailable_backup', 'initial_install_failure_recovery'],
        **before}, indent=2) + '\n')
    print('PASS: editor acceptance recorded for the exact browser assets and fixtures.')
