#!/usr/bin/env python3
"""Check actual Blender string-search semantics on the 32-bit WASM target."""
from setup_browser import CACHE,ROOT,toolchain,prepare_source,run
if __name__=='__main__':
    env=toolchain()
    source=prepare_source()
    build=CACHE/'string-ref-tests'
    build.mkdir(exist_ok=True)
    (build/'package.json').write_text('{"type":"commonjs"}\n')
    run('em++','-std=c++20','-O1','-I'+str(source/'source/blender/blenlib'),
        '-I'+str(CACHE/'wasm-threaded-sysroot/include'),ROOT/'tests/string_ref_wasm_probe.cc',
        '-o',build/'string-ref-probe.js',env=env)
    run(CACHE/'emsdk/node/22.16.0_64bit/bin/node',build/'string-ref-probe.js',env=env)
