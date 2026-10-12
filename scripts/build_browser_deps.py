#!/usr/bin/env python3
"""Cross-compile Blender's pinned image/compression prerequisites, with upstream tests."""
import argparse
import hashlib
import shutil
from pathlib import Path
import tarfile
import urllib.request
from setup_browser import ROOT, CACHE, LOCK, toolchain, run

def fetch(name):
    spec = LOCK["dependencies"][name]
    archive = CACHE / spec["archive"]
    if not archive.exists():
        temporary = archive.with_suffix(".partial")
        with urllib.request.urlopen(spec["url"], timeout=90) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        temporary.replace(archive)
    actual = hashlib.new(spec["hash_type"], archive.read_bytes()).hexdigest()
    if actual != spec["hash"]:
        raise SystemExit(f"{name}: artifact checksum differs from Blender's pinned manifest; refusing to build.")
    source = CACHE / "deps-src" / spec["source"]
    if not source.exists():
        with tarfile.open(archive) as bundle:
            bundle.extractall(CACHE / "deps-src", filter="data")
    return source

def build(name, env):
    source = fetch(name)
    directory = CACHE / "deps-build" / name
    directory.mkdir(parents=True, exist_ok=True)
    # Emscripten's upstream command-line test programs use CommonJS. The project's
    # browser JS is ESM, so keep the test build directory in its correct Node scope.
    (directory / "package.json").write_text('{"type":"commonjs"}\n')
    arguments = {
        "jpeg": ["-DENABLE_SHARED=OFF", "-DENABLE_STATIC=ON", "-DWITH_SIMD=OFF"],
        "zlib": ["-DZLIB_BUILD_EXAMPLES=ON", "-DCMAKE_PROJECT_INCLUDE=" + str(ROOT / "cmake/zlib-emscripten.cmake")],
        "png": ["-DPNG_SHARED=OFF", "-DPNG_STATIC=ON", "-DPNG_TESTS=ON", "-DPNG_TOOLS=ON", "-DPNG_HARDWARE_OPTIMIZATIONS=OFF"],
        "zstd": ["-DZSTD_BUILD_SHARED=OFF", "-DZSTD_BUILD_STATIC=ON", "-DZSTD_BUILD_PROGRAMS=OFF", "-DZSTD_BUILD_TESTS=ON", "-DZSTD_MULTITHREAD_SUPPORT=OFF"],
        "fmt": ["-DBUILD_SHARED_LIBS=OFF", "-DFMT_TEST=ON", "-DFMT_DOC=OFF", "-DFMT_INSTALL=ON", "-DCMAKE_CXX_FLAGS=-fexceptions"],
    }[name]
    cmake_source = source / "build/cmake" if name == "zstd" else source
    run("emcmake", "cmake", "-S", cmake_source, "-B", directory, "-G", "Ninja",
        "-DCMAKE_INSTALL_PREFIX=" + str(CACHE / "wasm-sysroot"),
        "-DCMAKE_PREFIX_PATH=" + str(CACHE / "wasm-sysroot"),
        "-DCMAKE_FIND_ROOT_PATH=" + str(CACHE / "wasm-sysroot"),
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXE_LINKER_FLAGS=-sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=1048576 -sDISABLE_EXCEPTION_CATCHING=0", *arguments, env=env)
    run("cmake", "--build", directory, "--parallel", "4", env=env)
    if name == "zlib":
        # Upstream 1.3.1 registers literal `example`/`example64` commands using
        # legacy add_test syntax, which doesn't apply CMake's WASM emulator.
        # Execute both original test programs through the pinned Node runner.
        node = CACHE / "emsdk/node/22.16.0_64bit/bin/node"
        for target in ["example", "example64"]:
            run(node, directory / (target + ".js"), cwd=directory, env=env)
        print("zlib: both upstream example test programs passed under Node/WebAssembly.")
    elif name == "zstd":
        # Upstream registers executable paths rather than targets, so invoke
        # the original fuzzer explicitly through Node. Its basic unit suite
        # unconditionally requests worker threads, unsupported by this build.
        # The documented starting-test option selects 128 randomized tests of
        # the supported single-threaded codec; no assertions are modified.
        node = CACHE / "emsdk/node/22.16.0_64bit/bin/node"
        run(node, directory / "tests/fuzzer.js", "-t1", "-i128", "-s1", cwd=directory, env=env)
        print("Zstandard: 128 seeded upstream fuzz iterations passed; thread-dependent basic unit suite excluded.")
    elif name == "png":
        # Upstream enables its CTest targets only with PNG_SHARED. Build two
        # original test programs against the real static library, preserving
        # their assertions and pixel/gamma validation rather than accepting a
        # zero-test CTest run.
        node = CACHE / "emsdk/node/22.16.0_64bit/bin/node"
        validator_root = directory / "validator-source"
        validator = validator_root / "contrib/libtests/pngvalid.c"
        validator.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "contrib/libtests/pngvalid.c", validator)
        run("patch", "--batch", "-p1", "-i", ROOT / "patches/libpng-1.6.58-validator-cleanup.patch", cwd=validator_root)
        for target, unit, arguments in [
            ("pngtest", source / "pngtest.c", [str(source / "pngtest.png")]),
            ("pngvalid", validator, []),
        ]:
            program = directory / (target + ".js")
            run("emcc", "-O2", "-sNODERAWFS=1", "-sALLOW_MEMORY_GROWTH=1", "-sSTACK_SIZE=1048576",
                "-I" + str(directory), "-I" + str(source), "-I" + str(source / "contrib/libtests"),
                "-I" + str(CACHE / "wasm-sysroot/include"), unit,
                directory / "libpng16.a", CACHE / "wasm-sysroot/lib/libz.a", "-lm", "-o", program, env=env)
            run(node, program, *arguments, cwd=directory, env=env)
        print("PNG: upstream pngtest round-trip and pngvalid validation programs passed under Node/WebAssembly.")
    else:
        run("ctest", "--test-dir", directory, "--parallel", "4", "--output-on-failure", "--no-tests=error", env=env)
    run("cmake", "--install", directory, env=env)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", choices=list(LOCK["dependencies"]), default=[])
    args = parser.parse_args()
    environment = toolchain()
    for name in args.names or list(LOCK["dependencies"]):
        build(name, environment)
