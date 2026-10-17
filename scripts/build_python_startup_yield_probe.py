#!/usr/bin/env python3
"""Exercise the production yield helper inside real nested CPython callbacks."""
import shutil
from setup_browser import ROOT, CACHE, toolchain, run

if __name__ == '__main__':
    prefix = CACHE / 'wasm-threaded-sysroot'
    archive = CACHE / 'python-browser/python313.zip'
    if not (prefix / 'python-runtime.json').exists() or not archive.exists():
        raise SystemExit('Build and validate embedded Python and its browser probe first.')
    out = CACHE / 'python-startup-yield-probe'
    out.mkdir(exist_ok=True)
    run('em++', ROOT / 'native/browser/python_startup_yield_probe.cc',
        '-I' + str(prefix / 'include/python3.13'), prefix / 'lib/libpython3.13.a',
        '-O2', '-g2', '-pthread', '-fexceptions', '-DPY_CALL_TRAMPOLINE',
        '-sUSE_ZLIB=1', '-sUSE_BZIP2=1', '--no-entry', '-sMODULARIZE=1',
        '-sEXPORT_NAME=createProbe', '-sENVIRONMENT=web,worker',
        '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864',
        '-sMAXIMUM_MEMORY=536870912', '-sSTACK_SIZE=4194304',
        '-sDEFAULT_PTHREAD_STACK_SIZE=2097152', '-sPTHREAD_POOL_SIZE=4',
        '-sPTHREAD_POOL_SIZE_STRICT=0', '-sASSERTIONS=2',
        '-sDISABLE_EXCEPTION_CATCHING=0', '-sASYNCIFY=1', '-sASYNCIFY_STACK_SIZE=2097152',
        '-sASYNCIFY_IMPORTS=@' + str(ROOT / 'cmake/python-asyncify-imports.json'),
        "-sEXPORTED_FUNCTIONS=['_probe_initialize','_probe_execute']",
        "-sEXPORTED_RUNTIME_METHODS=['ccall']",
        '--preload-file', str(archive) + '@/python/lib/python313.zip',
        '-o', out / 'probe.js', env=toolchain())
    shutil.copyfile(ROOT / 'native/browser/python_startup_yield_probe.html', out / 'index.html')
    shutil.copyfile(CACHE / 'python-browser/PYTHON-LICENSE.txt', out / 'PYTHON-LICENSE.txt')
    shutil.copyfile(ROOT / 'native/browser/LICENSE-GPL-3.0.txt', out / 'LICENSE.txt')
