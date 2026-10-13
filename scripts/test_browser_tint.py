#!/usr/bin/env python3
"""Run the real WASM Tint translator on Blender's validated SPIR-V."""
import hashlib
import json
from setup_browser import CACHE, toolchain, run

if __name__ == '__main__':
    env = toolchain()
    build = CACHE / 'deps-build/tint-threaded'
    probe = CACHE / 'shader-compiler-tests'
    run('cmake', '--build', build, '--target', 'blender_shader_translation_probe',
        '--parallel', '4', env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node',
        build / 'blender_shader_translation_probe.js', probe / 'blender-matrix.spv',
        probe / 'blender-matrix.wgsl', env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node',
        build / 'blender_shader_translation_probe.js', probe / 'atomic-composite.spv',
        probe / 'atomic-composite.wgsl', env=env)
    stamp = {name: hashlib.sha256((probe / name).read_bytes()).hexdigest()
             for name in ['blender-matrix.spv', 'blender-matrix.wgsl',
                          'atomic-composite.spv', 'atomic-composite.wgsl']}
    (probe / 'translation-validation.json').write_text(json.dumps(stamp, indent=2) + '\n')
