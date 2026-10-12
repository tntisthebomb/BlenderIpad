#!/usr/bin/env python3
"""Exercise the native WebGPU API used by a future Blender graphics backend."""
import hashlib
import json
from setup_browser import CACHE, ROOT, toolchain, run

if __name__ == '__main__':
    env = toolchain()
    build = CACHE / 'webgpu-native-probe'
    build.mkdir(exist_ok=True)
    shader = CACHE / 'shader-compiler-tests/blender-matrix.wgsl'
    if not shader.exists():
        raise SystemExit('Run the shader compiler and Tint acceptance checks first.')
    proof = shader.parent / 'translation-validation.json'
    if not proof.exists() or json.loads(proof.read_text()).get(shader.name) != hashlib.sha256(shader.read_bytes()).hexdigest():
        raise SystemExit('Shader differs from successful translation acceptance; rerun test_browser_tint.py.')
    run('em++', ROOT / 'tests/webgpu_native_probe.cc', '--use-port=emdawnwebgpu',
        '-std=c++20', '-O1', '-sASSERTIONS=2', '-sALLOW_MEMORY_GROWTH=1',
        '-sMODULARIZE=1', '-sEXPORT_NAME=createNativeWebGPU', '-sENVIRONMENT=web',
        '--preload-file', str(shader) + '@/blender-matrix.wgsl',
        '-o', build / 'webgpu-native.js', env=env)
    (build / 'index.html').write_text('''<!doctype html><html><body>
Native WebGPU acceptance harness; no Blender editor.
<script src="webgpu-native.js"></script><script>
createNativeWebGPU({onAbort:message => document.body.dataset.error=String(message)})
.catch(error => document.body.dataset.error=String(error));
</script></body></html>''')
