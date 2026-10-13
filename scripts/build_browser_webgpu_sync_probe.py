#!/usr/bin/env python3
"""Validate stack suspension for real synchronous Blender GPU readback calls."""
import argparse
import hashlib
import json
from setup_browser import CACHE, ROOT, toolchain, run
if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--python',action='store_true')
    args=parser.parse_args()
    env=toolchain()
    build=CACHE/('webgpu-python-sync-probe' if args.python else 'webgpu-sync-probe')
    build.mkdir(exist_ok=True)
    shader=CACHE/'shader-compiler-tests/blender-matrix.wgsl'
    proof=shader.parent/'translation-validation.json'
    if not shader.exists() or not proof.exists():
        raise SystemExit('Run shader translation acceptance before the GPU probe.')
    if json.loads(proof.read_text()).get(shader.name) != hashlib.sha256(shader.read_bytes()).hexdigest():
        raise SystemExit('Shader differs from validated translation; rerun test_browser_tint.py.')
    extra=[]
    if args.python:
        prefix=CACHE/'wasm-threaded-sysroot'
        extra=["-sASYNCIFY_IMPORTS=['_PyEM_TrampolineCall_JavaScript']",'-DBLENDER_SYNC_PYTHON','-DPY_CALL_TRAMPOLINE','-pthread',
               '-I'+str(prefix/'include/python3.13'),str(prefix/'lib/libpython3.13.a'),
               '-sUSE_ZLIB=1','-sUSE_BZIP2=1','-sENVIRONMENT=web,worker',
               '-sSTACK_SIZE=4194304','-sINITIAL_MEMORY=67108864',
               '-sDEFAULT_PTHREAD_STACK_SIZE=2097152','-sPTHREAD_POOL_SIZE=2',
               '-sPTHREAD_POOL_SIZE_STRICT=0','--preload-file',
               str(CACHE/'python-browser/python313.zip')+'@/python/lib/python313.zip']
    run('em++' ,ROOT/'tests/webgpu_sync_probe.cc','--use-port=emdawnwebgpu',
        '-std=c++20','-O1','-fexceptions','-sDISABLE_EXCEPTION_CATCHING=0',
        '-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=1048576','-sASSERTIONS=2',
        '-sALLOW_MEMORY_GROWTH=1','-sMODULARIZE=1','-sEXPORT_NAME=createNativeWebGPU',
        '-sENVIRONMENT=web',*extra,'--preload-file',str(shader)+'@/blender-matrix.wgsl',
        '-o',build/'webgpu-native.js',env=env)
    (build/'index.html').write_text('''<!doctype html><html><body>
Native synchronous WebGPU acceptance harness.
<script src="webgpu-native.js"></script><script>
createNativeWebGPU({onAbort:message => document.body.dataset.error=String(message)})
.catch(error => document.body.dataset.error=String(error));
</script></body></html>''')
