#!/usr/bin/env python3
"""Compare actual repeated suspension under combined and staged Binaryen."""
import subprocess
from setup_browser import CACHE, ROOT, toolchain, run


if __name__ == '__main__':
    env = toolchain()
    output = CACHE / 'binaryen-probe'
    output.mkdir(exist_ok=True)
    (output / 'package.json').write_text('{"type":"commonjs"}\n')
    node = CACHE / 'emsdk/node/22.16.0_64bit/bin/node'
    results = []
    for variant in ('combined', 'staged'):
        current = dict(env)
        if variant == 'combined':
            current.pop('EM_BINARYEN_ROOT')
        binary = output / (variant + '.js')
        run('emcc', ROOT / 'tests/binaryen_suspend_probe.c', '-O2',
            '-sASYNCIFY=1', '-sASSERTIONS=2', '-sENVIRONMENT=node',
            '-o', binary, env=current)
        result = subprocess.check_output([str(node), str(binary)], cwd=output, env=current, text=True)
        if result.strip() != 'PASS: resumed exact state 21':
            raise SystemExit('Suspension/state acceptance failed: ' + result)
        results.append(result)
    if results[0] != results[1]:
        raise SystemExit('Combined and staged optimizer outputs differ.')
    prefix = CACHE / 'wasm-threaded-sysroot'
    stdlib = CACHE / 'python-browser/python313.zip'
    if not stdlib.exists():
        raise SystemExit('Build the real Python runtime and browser probe first.')
    python_results = []
    for variant in ('combined', 'staged'):
        current = dict(env)
        if variant == 'combined':
            current.pop('EM_BINARYEN_ROOT')
        binary = output / ('python-' + variant + '.js')
        run('emcc', ROOT / 'tests/binaryen_python_probe.c',
            '-I' + str(prefix / 'include/python3.13'), prefix / 'lib/libpython3.13.a',
            '-O2', '-g2', '-pthread', '-fexceptions', '-DPY_CALL_TRAMPOLINE', '-UNDEBUG',
            '-sASYNCIFY=1', '-sASSERTIONS=2', '-sDISABLE_EXCEPTION_CATCHING=0',
            '-sENVIRONMENT=node', '-sALLOW_MEMORY_GROWTH=1', '-sSTACK_SIZE=8388608',
            '-sASYNCIFY_STACK_SIZE=2097152', '-sUSE_ZLIB=1', '-sUSE_BZIP2=1',
            '-sASYNCIFY_IMPORTS=@' + str(ROOT / 'cmake/python-asyncify-imports.json'),
            '--preload-file', str(stdlib) + '@/python/lib/python313.zip',
            '-o', binary, env=current)
        result = subprocess.check_output([str(node), str(binary)], cwd=output, env=current, text=True)
        expected = 'PASS: CPython imports, class calls, recursion and repeated suspension'
        if result.strip() != expected:
            raise SystemExit('Real Python suspension acceptance failed: ' + result)
        python_results.append(result)
    if python_results[0] != python_results[1]:
        raise SystemExit('Combined and staged Python results differ.')
    print('PASS: staged Binaryen preserves repeated suspension and state assertions.')
