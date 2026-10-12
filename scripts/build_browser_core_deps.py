#!/usr/bin/env python3
"""Compile the stable-release dependency graph for the real Blender core.

Libraries without an upstream WASM test route are not labeled runtime-validated;
their integration must pass the full application's image/font/color smoke tests.
"""
import argparse
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from setup_browser import CACHE, ROOT, toolchain, run
from build_browser_deps import fetch, build

RECIPES = {
    "brotli": ["-DBROTLI_WRAPPER=" + str(CACHE / "emsdk/node/22.16.0_64bit/bin/node")],
    "freetype": ["-DFT_DISABLE_HARFBUZZ=ON", "-DFT_DISABLE_BZIP2=ON", "-DFT_REQUIRE_BROTLI=ON", "-DFT_REQUIRE_ZLIB=ON", "-DFT_REQUIRE_PNG=ON"],
    "imath": ["-DBUILD_TESTING=ON", "-DPYTHON=OFF", "-DIMATH_INSTALL_PKG_CONFIG=ON"],
    "robinmap": ["-DTSL_ROBIN_MAP_ENABLE_TESTS=OFF"],
    "yamlcpp": ["-DYAML_CPP_BUILD_TESTS=OFF", "-DYAML_CPP_BUILD_TOOLS=OFF"],
    "pystring": [],
    "expat": ["-DEXPAT_BUILD_TOOLS=OFF", "-DEXPAT_BUILD_EXAMPLES=OFF", "-DEXPAT_BUILD_TESTS=OFF", "-DEXPAT_SHARED_LIBS=OFF"],
    "minizipng": ["-DMZ_COMPAT=OFF", "-DMZ_ZLIB=ON", "-DMZ_BZIP2=OFF", "-DMZ_LZMA=OFF", "-DMZ_ZSTD=OFF", "-DMZ_OPENSSL=OFF", "-DMZ_LIBBSD=OFF", "-DMZ_PKCRYPT=OFF", "-DMZ_WZAES=OFF", "-DMZ_BUILD_TESTS=OFF", "-DMZ_BUILD_UNIT_TESTS=OFF", "-DMZ_FETCH_LIBS=OFF"],
    "eigen": ["-DBUILD_TESTING=OFF", "-DEIGEN_BUILD_DOC=OFF"],
    "openjph": ["-DOJPH_BUILD_EXECUTABLES=OFF", "-DOJPH_BUILD_TESTS=OFF", "-DOJPH_ENABLE_TIFF_SUPPORT=OFF"],
    "openexr": ["-DBUILD_TESTING=OFF", "-DOPENEXR_BUILD_TOOLS=OFF", "-DOPENEXR_BUILD_EXAMPLES=OFF", "-DOPENEXR_INSTALL_EXAMPLES=OFF", "-DOPENEXR_INSTALL_TOOLS=OFF", "-DOPENEXR_FORCE_INTERNAL_IMATH=OFF"],
    "tiff": ["-Dtiff-tools=OFF", "-Dtiff-tests=OFF", "-Dtiff-docs=OFF", "-Dtiff-contrib=OFF", "-Dlzma=OFF", "-Djbig=OFF", "-Dlerc=OFF", "-Dwebp=OFF", "-Dzstd=ON"],
    "opencolorio": ["-DOCIO_INSTALL_EXT_PACKAGES=NONE", "-DOCIO_BUILD_APPS=OFF", "-DOCIO_BUILD_TESTS=OFF", "-DOCIO_BUILD_GPU_TESTS=OFF", "-DOCIO_BUILD_DOCS=OFF", "-DOCIO_BUILD_PYTHON=OFF", "-DOCIO_BUILD_OPENFX=OFF", "-DOCIO_USE_SSE=OFF", "-DOCIO_BUILD_FROZEN_DOCS=OFF"],
    "openimageio": ["-DLINKSTATIC=ON", "-DOIIO_BUILD_TESTS=OFF", "-DOIIO_BUILD_TOOLS=OFF", "-DBUILD_DOCS=OFF", "-DINSTALL_DOCS=OFF", "-DUSE_PYTHON=OFF", "-DUSE_QT=OFF", "-DUSE_OPENGL=OFF", "-DUSE_FREETYPE=OFF", "-DUSE_OPENCV=OFF", "-DUSE_TBB=OFF", "-DUSE_BZIP2=OFF", "-DBUILD_MISSING_DEPS=OFF", "-DBUILD_MISSING_FMT=OFF", "-DBUILD_MISSING_ROBINMAP=OFF", "-DSTOP_ON_WARNING=OFF", "-DENABLE_PNG=ON", "-DENABLE_JPEG=ON", "-DENABLE_OpenEXR=ON", "-DENABLE_TIFF=ON", *["-DENABLE_" + x + "=OFF" for x in ["GIF", "FFMPEG", "HEIF", "Raw", "WebP", "OpenJPEG", "Ptex", "DICOM", "Field3D", "OpenVDB", "DDS", "R3DSDK", "Nuke", "LIBHEIF", "BZip2"]]],
}

def core_build(name, env):
    source = fetch(name)
    prefix = CACHE / "wasm-threaded-sysroot"
    directory = CACHE / "deps-build" / (name + "-threaded")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "package.json").write_text('{"type":"commonjs"}\n')
    cmake_source = source / "expat" if name == "expat" else source
    if name == "pystring":
        # Stable Blender supplies this missing upstream build file itself.
        cmake_source = directory / "source"
        cmake_source.mkdir(exist_ok=True)
        inputs = {"pystring.cpp": source / "pystring.cpp", "pystring.h": source / "pystring.h",
                  "CMakeLists.txt": CACHE / "blender/build_files/build_environment/patches/cmakelists_pystring.txt"}
        for filename, original in inputs.items():
            target = cmake_source / filename
            if target.exists() and target.read_bytes() != original.read_bytes():
                raise SystemExit("Preserve local edits before regenerating pystring's build source: " + filename)
            shutil.copyfile(original, target)
    options = list(RECIPES[name])
    if name == "openimageio":
        staged = directory / "port-source"
        with tempfile.TemporaryDirectory(prefix="oiio-patch-", dir=CACHE) as temporary:
            expected = Path(temporary)
            for filename in ["strutil.cpp", "sysutil.cpp", "ustring.cpp"]:
                relative = "src/libutil/" + filename
                (expected / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, expected / relative)
            run("patch", "--batch", "-p1", "-i", ROOT / "patches/openimageio-3.1.13.1-emscripten.patch", cwd=expected)
            for filename in ["strutil.cpp", "sysutil.cpp", "ustring.cpp"]:
                relative = "src/libutil/" + filename
                target = staged / relative
                if target.exists() and target.read_bytes() != (expected / relative).read_bytes():
                    raise SystemExit("Preserve local edits in OpenImageIO's port overlay: " + relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(expected / relative, target)
        options.append("-DBLENDER_PORT_OIIO_SOURCE_DIR=" + str(staged))
    run("emcmake", "cmake", "-S", cmake_source, "-B", directory, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF",
        "-DCMAKE_INSTALL_PREFIX=" + str(prefix), "-DCMAKE_PREFIX_PATH=" + str(prefix),
        "-DCMAKE_FIND_ROOT_PATH=" + str(prefix),
        "-DCMAKE_PROJECT_INCLUDE=" + str(ROOT / "cmake/threaded-emscripten.cmake"),
        "-DCMAKE_C_FLAGS=-pthread -fexceptions", "-DCMAKE_CXX_FLAGS=-pthread -fexceptions",
        "-DCMAKE_EXE_LINKER_FLAGS=-pthread -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=4194304 -sDISABLE_EXCEPTION_CATCHING=0 -sASSERTIONS=2",
        *options, env=env)
    run("cmake", "--build", directory, "--parallel", "4", env=env)
    if name == "brotli":
        run("ctest", "--test-dir", directory, "--parallel", "2", "--output-on-failure", "--no-tests=error", env=env)
    elif name == "imath":
        # Upstream uses executable paths in add_test, bypassing CMake's emulator.
        # Run every registered command, preserving its original arguments.
        manifest = json.loads(subprocess.check_output(
            ["ctest", "--test-dir", str(directory), "--show-only=json-v1"], env=env, text=True))
        if not manifest["tests"]:
            raise SystemExit("Imath registered no tests")
        node = CACHE / "emsdk/node/22.16.0_64bit/bin/node"
        for test in manifest["tests"]:
            command = test["command"]
            target = Path(command[0])
            if target.parent != directory / "bin" or target.name not in {"ImathTest.js", "ImathHalfCTest.js", "ImathHalfPerfTest.js"}:
                raise SystemExit("Unexpected Imath test command: " + test["name"])
            run(node, *command, cwd=directory, env=env)
        print(f"Imath: {len(manifest['tests'])} original registered test commands passed via Node.", flush=True)
    else:
        print(name + ": compiled; application-level runtime validation pending.", flush=True)
    run("cmake", "--install", directory, env=env)
    if name == "brotli":
        # Upstream 1.0.9 intentionally omits installation for Emscripten.
        # Stage the verified static libraries under the downstream find names.
        (prefix / "lib/pkgconfig").mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / "c/include/brotli", prefix / "include/brotli", dirs_exist_ok=True)
        for component in ["common", "dec", "enc"]:
            shutil.copyfile(directory / ("libbrotli" + component + "-static.a"), prefix / "lib" / ("libbrotli" + component + ".a"))
            extra = "" if component == "common" else " -lbrotlicommon"
            (prefix / "lib/pkgconfig" / ("libbrotli" + component + ".pc")).write_text(
                "prefix=" + str(prefix) + "\nlibdir=${prefix}/lib\nincludedir=${prefix}/include\n"
                "Name: libbrotli" + component + "\nDescription: Brotli static " + component +
                "\nVersion: 1.0.9\nLibs: -L${libdir} -lbrotli" + component + extra + "\nCflags: -I${includedir}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", choices=["jpeg", "png", "zlib", "zstd", "fmt", *RECIPES], default=[])
    args = parser.parse_args()
    env = toolchain()
    prefix = CACHE / "wasm-threaded-sysroot"
    env.update({"PKG_CONFIG_LIBDIR": str(prefix / "lib/pkgconfig"), "PKG_CONFIG_PATH": ""})
    sequence = args.names or ["zlib", "jpeg", "png", "zstd", "fmt", *RECIPES]
    for name in sequence:
        if name in RECIPES:
            core_build(name, env)
        else:
            build(name, env, threaded=True)
