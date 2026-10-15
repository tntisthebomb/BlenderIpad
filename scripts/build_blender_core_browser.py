#!/usr/bin/env python3
"""Relink native Blender for the browser, including its GUI with --editor."""
import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
from setup_browser import CACHE, ROOT, toolchain, run
from browser_runtime_scripts import stage_runtime_scripts

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--webgpu',action='store_true')
    parser.add_argument('--editor',action='store_true')
    options=parser.parse_args()
    if options.editor:
        options.webgpu=True
    env = toolchain()
    core = CACHE / ('blender-webgpu-build' if options.webgpu else 'blender-core-build')
    stamp = core / 'core-validation.json'
    if not stamp.exists():
        raise SystemExit('Build and validate background Blender first.')
    validated = json.loads(stamp.read_text())
    if validated.get('scene_test_sha256') != hashlib.sha256((ROOT / 'tests/blender_core_scene.py').read_bytes()).hexdigest():
        raise SystemExit('The scene test changed; rerun CLI acceptance before browser packaging.')
    for name, expected in validated['files'].items():
        if hashlib.sha256((core / 'bin' / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('The background binary changed; rerun its actual scene test first.')
    stdlib = CACHE / 'python-browser/python313.zip'
    if not stdlib.exists():
        raise SystemExit('Build the Python browser probe to package its standard library.')
    output = CACHE / ('blender-webgpu-browser' if options.webgpu else 'blender-core-browser')
    output.mkdir(exist_ok=True)
    commands = subprocess.check_output(['ninja', '-t', 'commands', 'bin/blender.js'],
                                       cwd=core, env=env, text=True).splitlines()
    links = [line for line in commands if ' -o bin/blender.js ' in line]
    if len(links) != 1:
        raise SystemExit('Expected exactly one actual Blender link command.')
    args = shlex.split(links[0])
    args = args[args.index('&&') + 1:args.index('&&', args.index('&&') + 1)]
    if '-sNODERAWFS=1' not in args or '-sENVIRONMENT=node' not in args:
        raise SystemExit('Unrecognized CLI build; refusing to silently reuse host I/O.')
    args.remove('-sNODERAWFS=1')
    args[args.index('-sENVIRONMENT=node')] = '-sENVIRONMENT=web,worker'
    args[args.index('--pre-js') + 1] = str(ROOT / 'native/browser/core_browser_env.js')
    args[args.index('-o') + 1] = str(output / 'blender-core.js')
    scripts = stage_runtime_scripts(core)
    args += ['-sMODULARIZE=1', '-sEXPORT_NAME=createBlenderCore',
             "-sEXPORTED_RUNTIME_METHODS=['callMain','FS','runtimeKeepalivePush','runtimeKeepalivePop']", '-sFORCE_FILESYSTEM=1',
             '--preload-file', str(stdlib) + '@/python/lib/python313.zip',
             '--preload-file', str(scripts) + '@/blender/scripts',
             '--preload-file', str(CACHE / 'blender-browser/release/datafiles') + '@/blender/datafiles',
             '--preload-file', str(ROOT / 'tests/blender_core_scene.py') + '@/scene_test.py']
    if options.webgpu:
        args += ['--preload-file', str(ROOT / 'tests/blender_gpu_scene.py') + '@/gpu_test.py']
    if options.editor:
        args += ['-lidbfs.js','--pre-js', str(ROOT / 'native/browser/editor_browser_env.js')]
        args += ['--preload-file', str(ROOT / 'native/browser/editor_startup.py') + '@/browser_startup.py']
        args += ['--preload-file', str(ROOT / 'tests/blender_editor_scene.py') + '@/editor_test.py']
    run(*args, cwd=core, env=env)
    shutil.copyfile(ROOT / ('native/browser/blender_webgpu.html' if options.webgpu else 'native/browser/blender_core.html'), output / 'core.html')
    if options.editor:
        shutil.copyfile(ROOT / 'native/browser/blender_editor.html', output / 'editor.html')
        shutil.copyfile(output / 'editor.html', output / 'index.html')
        for name in ('manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','editor_files.js','editor_input.js','ipad-startup.html'):
            shutil.copyfile(ROOT / 'native/browser' / name, output / name)
        content=hashlib.sha256()
        for name in ('index.html','editor.html','blender-core.js','blender-core.wasm',
                     'blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','editor_files.js','editor_input.js','ipad-startup.html'):
            content.update(name.encode())
            with (output / name).open('rb') as stream:
                while chunk := stream.read(1024*1024):
                    content.update(chunk)
        worker=(ROOT / 'native/browser/service-worker.js').read_text()
        content.update(worker.encode())
        (output / 'service-worker.js').write_text(worker.replace('__BUILD_CACHE__','blender-ipad-'+content.hexdigest()))
    print('Linked experimental browser Blender. Editor, renderer and durable-storage acceptance remain outstanding.')
