#!/usr/bin/env python3
"""Validate the combined image, colour and font libraries against Blender assets."""
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

if __name__ == "__main__":
    env = toolchain()
    source = prepare_source(materialize_assets=True)
    prefix = CACHE / "wasm-threaded-sysroot"
    build = CACHE / "core-dependency-tests"
    build.mkdir(exist_ok=True)
    (build / "package.json").write_text('{"type":"commonjs"}\n')
    run("emcmake", "cmake", "-S", ROOT / "native/core-dependency-tests", "-B", build, "-G", "Ninja",
        "-DBROWSER_RUNTIME_PREFIX=" + str(prefix),
        "-DCMAKE_PREFIX_PATH=" + str(prefix), "-DCMAKE_FIND_ROOT_PATH=" + str(prefix),
        "-DCMAKE_PROJECT_INCLUDE=" + str(ROOT / "cmake/threaded-emscripten.cmake"),
        "-DCMAKE_C_FLAGS=-pthread -fexceptions", "-DCMAKE_CXX_FLAGS=-pthread -fexceptions",
        "-DCMAKE_EXE_LINKER_FLAGS=-pthread -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=67108864 -sSTACK_SIZE=4194304 -sDEFAULT_PTHREAD_STACK_SIZE=2097152 -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0", env=env)
    run("cmake", "--build", build, "--parallel", "4", env=env)
    run(CACHE / "emsdk/node/22.16.0_64bit/bin/node", build / "core-dependencies-probe.js",
        source / "release/datafiles", build / "outputs", env=env)
