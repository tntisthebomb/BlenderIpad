#!/usr/bin/env python3
"""Build Blender's pinned CPU OpenSubdiv and run its upstream regression tests."""
import hashlib
import json
from pathlib import Path
import subprocess
from setup_browser import CACHE, ROOT, toolchain, run
from build_browser_deps import fetch


if __name__ == '__main__':
    env = toolchain()
    source = fetch('opensubdiv')
    build = CACHE / 'deps-build/opensubdiv-threaded'
    build.mkdir(parents=True, exist_ok=True)
    (build / 'package.json').write_text('{"type":"commonjs"}\n')
    flags = ['-DBUILD_SHARED_LIBS=OFF', '-DNO_EXAMPLES=ON', '-DNO_TUTORIALS=ON',
             '-DNO_REGRESSION=OFF', '-DNO_TESTS=OFF', '-DNO_GLTESTS=ON',
             '-DOSD_PATCH_SHADER_SOURCE_GLSL=ON']
    flags += ['-DNO_' + name + '=ON' for name in
              ('PTEX', 'DOC', 'OMP', 'TBB', 'CUDA', 'OPENCL', 'CLEW', 'OPENGL', 'METAL', 'DX', 'GLFW')]
    prefix = CACHE / 'wasm-threaded-sysroot'
    run('emcmake', 'cmake', '-S', source, '-B', build, '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
        '-DCMAKE_POSITION_INDEPENDENT_CODE=OFF',
        '-DCMAKE_PROJECT_INCLUDE=' + str(ROOT / 'cmake/threaded-emscripten.cmake'),
        '-DCMAKE_C_FLAGS=-pthread -fexceptions -UNDEBUG',
        '-DCMAKE_CXX_FLAGS=-pthread -fexceptions -UNDEBUG',
        '-DCMAKE_EXE_LINKER_FLAGS=-pthread -sNODERAWFS=1 -sASSERTIONS=2 '
        '-sALLOW_MEMORY_GROWTH=1 -sDISABLE_EXCEPTION_CATCHING=0 -sSTACK_SIZE=8388608',
        *flags, env=env)
    run('cmake', '--build', build, '--parallel', '4', env=env)
    # Upstream registers literal executable paths, bypassing CMake's emulator.
    # Make them discoverable, then run JS with Node and all original arguments.
    for binary in (build / 'bin').glob('*.js'):
        bare = binary.with_suffix('')
        if not bare.exists():
            bare.symlink_to(binary.name)
    tests = json.loads(subprocess.check_output(
        ['ctest', '--test-dir', str(build), '--show-only=json-v1'], env=env, text=True))['tests']
    if not tests:
        raise SystemExit('OpenSubdiv upstream tests are missing.')
    for test in tests:
        command = list(test['command'])
        executable = Path(command[0])
        if executable.with_suffix('.js').exists():
            command[0] = str(executable.with_suffix('.js'))
        run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', *command,
            cwd=build, env=env, timeout=120)
        print('PASS upstream ' + test['name'], flush=True)
    run('cmake', '--install', build, env=env)
    (build / 'validation.json').write_text(json.dumps({
        'scope': 'CPU OpenSubdiv upstream tests; application modifier acceptance is separate',
        'checks': [test['name'] for test in tests],
        'libraries': {name: hashlib.sha256((prefix / 'lib' / name).read_bytes()).hexdigest()
                      for name in ('libosdCPU.a', 'libosdGPU.a')},
    }, indent=2) + '\n')
