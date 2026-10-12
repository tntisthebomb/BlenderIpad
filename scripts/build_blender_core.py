#!/usr/bin/env python3
"""Configure/build the actual stable Blender background application with bpy."""
import argparse
import hashlib
import json
import subprocess
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

def host_shader_tool(source):
    directory = source / "source/blender/gpu/shader_tool"
    build = CACHE / "host-shader-tool"
    build.mkdir(exist_ok=True)
    executable = build / "shader_tool"
    stamp = build / "build.json"
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    inputs = {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.rglob("*")) if p.suffix in {".cc", ".hh"}}
    previous = json.loads(stamp.read_text()) if stamp.exists() else {}
    if executable.exists():
        if not previous or hashlib.sha256(executable.read_bytes()).hexdigest() != previous.get("binary_sha256"):
            raise SystemExit("Preserve unrecognized edits to the host shader tool before rebuilding.")
    if previous.get("inputs") != inputs or previous.get("compiler") != compiler:
        temporary = build / "shader_tool.new"
        run("g++", "-std=c++20", "-O2", "-I" + str(directory), "-I" + str(directory / "lexit"),
            *sorted(directory.glob("*.cc")), *sorted((directory / "lexit").glob("*.cc")), "-o", temporary)
        temporary.replace(executable)
        stamp.write_text(json.dumps({"inputs": inputs, "compiler": compiler,
            "binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}, indent=2) + "\n")
    return executable

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    env = toolchain()
    source = prepare_source(materialize_assets=True)
    shader_tool = host_shader_tool(source)
    prefix = CACHE / "wasm-threaded-sysroot"
    build = CACHE / "blender-core-build"
    build.mkdir(exist_ok=True)
    (build / "package.json").write_text('{"type":"commonjs"}\n')
    flags = "-pthread -fexceptions -DPY_CALL_TRAMPOLINE -UNDEBUG"
    link = "-pthread -sNODERAWFS=1 -sENVIRONMENT=node -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=134217728 -sMAXIMUM_MEMORY=1073741824 -sSTACK_SIZE=8388608 -sDEFAULT_PTHREAD_STACK_SIZE=2097152 -sUSE_ZLIB=1 -sUSE_BZIP2=1 --pre-js " + str(ROOT / "native/browser/core_node_env.js")
    run("emcmake", "cmake", "-S", source, "-B", build, "-G", "Ninja",
        "-DBROWSER_RUNTIME_PREFIX=" + str(prefix),
        "-DBROWSER_HOST_PYTHON=" + str(CACHE / "deps-build/python-host/python"),
        "-DBLENDER_HOST_SHADER_TOOL=" + str(shader_tool),
        "-C", ROOT / "cmake/browser-core.cmake",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_PREFIX_PATH=" + str(prefix),
        "-DCMAKE_FIND_ROOT_PATH=" + str(prefix),
        "-DCMAKE_PROJECT_INCLUDE=" + str(ROOT / "cmake/threaded-emscripten.cmake"),
        "-DCMAKE_C_FLAGS=" + flags, "-DCMAKE_CXX_FLAGS=" + flags,
        "-DCMAKE_EXE_LINKER_FLAGS=" + link, env=env)
    if not args.configure_only:
        run("cmake", "--build", build, "--target", "blender", "--parallel", "4", env=env)
