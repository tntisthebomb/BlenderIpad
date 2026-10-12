#!/usr/bin/env python3
"""Relink the actual background Blender objects for a browser integration test.

This is deliberately not a GUI build or the downloadable iPad workbench.
"""
import hashlib
import json
import shlex
import shutil
import subprocess
from setup_browser import CACHE, ROOT, toolchain, run

if __name__ == '__main__':
    env = toolchain()
    core = CACHE / 'blender-core-build'
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
    output = CACHE / 'blender-core-browser'
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
    args += ['-sMODULARIZE=1', '-sEXPORT_NAME=createBlenderCore',
             "-sEXPORTED_RUNTIME_METHODS=['callMain','FS']", '-sFORCE_FILESYSTEM=1',
             '--preload-file', str(stdlib) + '@/python/lib/python313.zip',
             '--preload-file', str(CACHE / 'blender-browser/scripts') + '@/blender/scripts',
             '--preload-file', str(CACHE / 'blender-browser/release/datafiles') + '@/blender/datafiles',
             '--preload-file', str(ROOT / 'tests/blender_core_scene.py') + '@/scene_test.py']
    run(*args, cwd=core, env=env)
    shutil.copyfile(ROOT / 'native/browser/blender_core.html', output / 'core.html')
    print('Linked browser background Blender. Editor, rendering and durable storage are still pending.')
