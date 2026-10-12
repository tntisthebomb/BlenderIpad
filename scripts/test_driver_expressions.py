#!/usr/bin/env python3
"""Compile and exercise the real expression parser/evaluator, with its allocator."""
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

if __name__ == "__main__":
    env = toolchain()
    source = prepare_source()
    build = CACHE / "driver-expression-tests"
    build.mkdir(exist_ok=True)
    (build / "package.json").write_text('{"type":"commonjs"}\n')
    library = CACHE / "ghost-build/libblender_browser_ghost.a"
    if not library.exists():
        raise SystemExit("Build the GHOST platform's actual allocator library first.")
    run("em++", ROOT / "tests/driver_expression_probe.cc",
        source / "source/blender/blenlib/intern/expr_pylike_eval.cc", library,
        source / "source/blender/blenlib/intern/BLI_assert.cc",
        source / "source/blender/blenlib/intern/system.cc",
        "-I" + str(source / "source/blender/blenlib"),
        "-I" + str(source / "intern/guardedalloc"), "-I" + str(source / "intern/clog"),
        "-std=c++20", "-O1", "-g", "-fexceptions", "-sASSERTIONS=2", "-sDISABLE_EXCEPTION_CATCHING=0",
        "-sALLOW_MEMORY_GROWTH=1", "-sSTACK_SIZE=1048576", "-sEXIT_RUNTIME=1",
        "-o", build / "probe.js", env=env)
    run(CACHE / "emsdk/node/22.16.0_64bit/bin/node", build / "probe.js", env=env)
