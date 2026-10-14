#!/usr/bin/env python3
"""Build the pinned real oneTBB scheduler; validate before installing it."""
from setup_browser import CACHE,ROOT,toolchain,run
from build_browser_deps import fetch
import json
import hashlib

def build():
    env=toolchain();source=fetch('tbb');directory=CACHE/'deps-build/tbb-threaded'
    run('emcmake','cmake','-S',source,'-B',directory,'-G','Ninja',
        '-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DTBB_TEST=OFF',
        '-DTBBMALLOC_BUILD=OFF','-DTBBMALLOC_PROXY_BUILD=OFF','-DTBB_DISABLE_HWLOC_AUTOMATIC_SEARCH=ON',
        '-DCMAKE_PROJECT_INCLUDE='+str(ROOT/'cmake/tbb-emscripten.cmake'),
        '-DCMAKE_C_FLAGS=-pthread -fexceptions','-DCMAKE_CXX_FLAGS=-pthread -fexceptions',
        '-DCMAKE_POSITION_INDEPENDENT_CODE=OFF',
        '-DCMAKE_INSTALL_PREFIX='+str(CACHE/'wasm-threaded-sysroot'),env=env)
    run('cmake','--build',directory,'--target','tbb','--parallel','4',env=env)
    libraries=list(directory.rglob('libtbb.a'))
    if len(libraries)!=1: raise SystemExit('Expected exactly one static oneTBB library.')
    probe=CACHE/'tbb-probe';probe.mkdir(exist_ok=True)
    (probe/'package.json').write_text('{"type":"commonjs"}\n')
    flags=['-std=c++17','-O2','-UNDEBUG','-DTBB_USE_ASSERT=1','-I'+str(source/'include'),
           str(libraries[0]),'-pthread','-fexceptions','-sPTHREAD_POOL_SIZE=4',
           '-sPTHREAD_POOL_SIZE_STRICT=2','-sASSERTIONS=2','-sEXIT_RUNTIME=1',
           '-sDISABLE_EXCEPTION_CATCHING=0','-sALLOW_MEMORY_GROWTH=1',
           '-sSTACK_SIZE=8388608','-sDEFAULT_PTHREAD_STACK_SIZE=2097152']
    run('em++',ROOT/'tests/tbb_runtime_probe.cc',*flags,'-sENVIRONMENT=node','-sNODERAWFS=1',
        '-o',probe/'node.js',env=env)
    run(CACHE/'emsdk/node/22.16.0_64bit/bin/node',probe/'node.js',env=env)
    run('em++',ROOT/'tests/tbb_runtime_probe.cc',*flags,'-sENVIRONMENT=web,worker',
        '-sMODULARIZE=1','-sEXPORT_NAME=createTBBProbe',"-sEXPORTED_RUNTIME_METHODS=['callMain']",
        '-o',probe/'browser.js',env=env)
    (probe/'index.html').write_text('''<!doctype html><body><script src="browser.js"></script><script>
    window.output=[];
    createTBBProbe({noInitialRun:true,print:text=>output.push(text),
      onAbort:error=>document.body.dataset.error=String(error),
      onExit:code=>document.body.dataset.exit=String(code)}).then(module=>{
        window.tbb=module;document.body.dataset.ready='true';
    }).catch(error=>document.body.dataset.error=String(error));
    </script></body>''')
    run(CACHE/'browser-tests/bin/python',ROOT/'tests/tbb_runtime_browser_test.py',env=env)
    run('cmake','--install',directory,env=env)
    (probe/'validation.json').write_text(json.dumps({'checks':['native_thread_tasks','browser_offline_tasks'],
        'scope':'oneTBB scheduler, not Cycles rendering',
        'library_sha256':hashlib.sha256((CACHE/'wasm-threaded-sysroot/lib/libtbb.a').read_bytes()).hexdigest(),
        'probe_sha256':hashlib.sha256((ROOT/'tests/tbb_runtime_probe.cc').read_bytes()).hexdigest()},indent=2)+'\n')

if __name__=='__main__': build()
