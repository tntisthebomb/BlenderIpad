#!/usr/bin/env python3
"""Configure/build the actual stable Blender background application with bpy."""
import argparse
import hashlib
import json
import subprocess
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

def link_prerequisites(build, env):
    """Build the link's complete object/archive inputs without a redundant CLI link."""
    query = subprocess.check_output(['ninja', '-t', 'query', 'bin/blender.js'],
                                    cwd=build, env=env, text=True)
    if 'input: CXX_EXECUTABLE_LINKER__blender_Release' not in query:
        raise SystemExit('Unrecognized native application link rule')
    inputs = []
    for line in query.split('  outputs:', 1)[0].splitlines():
        if not line.startswith('    '): continue
        name = line.strip().removeprefix('|| ').removeprefix('| ')
        if name.endswith(('.o', '.a')) and name not in inputs: inputs.append(name)
    if not any(name.endswith('.o') for name in inputs) or len(inputs) < 20:
        raise SystemExit('Incomplete application link prerequisites')
    run('ninja', '-j4', *inputs, cwd=build, env=env)

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
    parser.add_argument("--webgpu", action="store_true", help="Experimental GPU backend integration profile; editor remains headless")
    parser.add_argument("--objects-only", action="store_true", help="Build all application link inputs; the browser engine is linked and validated separately")
    parser.add_argument("--gpu-library-only", action="store_true", help="Compile real GPU interfaces before application linking")
    parser.add_argument("--editor",action="store_true",help="Experimental actual editor with GHOST WebGPU window")
    parser.add_argument("--cycles",action="store_true",help="Experimental scalar CPU Cycles with the validated browser oneTBB scheduler")
    args = parser.parse_args()
    if args.editor: args.webgpu=True
    env = toolchain()
    source = prepare_source(materialize_assets=True)
    shader_tool = host_shader_tool(source)
    prefix = CACHE / "wasm-threaded-sysroot"
    build = CACHE / ("blender-webgpu-build" if args.webgpu else "blender-core-build")
    build.mkdir(exist_ok=True)
    (build / "package.json").write_text('{"type":"commonjs"}\n')
    flags = "-pthread -fexceptions -DPY_CALL_TRAMPOLINE -UNDEBUG"
    link = "-g2 -pthread -sNODERAWFS=1 -sENVIRONMENT=node -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=134217728 -sMAXIMUM_MEMORY=1073741824 -sSTACK_SIZE=8388608 -sDEFAULT_PTHREAD_STACK_SIZE=2097152 -sUSE_ZLIB=1 -sUSE_BZIP2=1 --pre-js " + str(ROOT / "native/browser/core_node_env.js")
    if args.webgpu:
        # Optimize the linked module before and after suspension instrumentation.
        # CPython's evaluation loop otherwise exceeds ordinary engine stack limits.
        link += " -O2 -sASYNCIFY=1 -sASYNCIFY_STACK_SIZE=2097152 -sASYNCIFY_IMPORTS=@" + str(ROOT / "cmake/python-asyncify-imports.json") + " -sASYNCIFY_REMOVE=@" + str(ROOT / "cmake/asyncify-cpu-initializers.json")
        # Binaryen otherwise merges singly-called registration units back
        # together, creating functions too large for browser compilers.
        link += " -sBINARYEN_EXTRA_PASSES=--one-caller-inline-max-function-size=0"
    graphics = []
    graphics += ["-DWITH_CYCLES=" + ("ON" if args.cycles else "OFF"),
                 "-DWITH_CYCLES_STANDALONE=OFF",
                 "-DWITH_OPENSUBDIV=ON",
                 "-DWITH_TBB=" + ("ON" if args.cycles else "OFF")]
    subdivision_proof = CACHE / 'deps-build/opensubdiv-threaded/validation.json'
    if not subdivision_proof.exists():
        raise SystemExit('Build and validate browser OpenSubdiv before enabling mesh subdivision.')
    for name, expected in json.loads(subdivision_proof.read_text())['libraries'].items():
        if hashlib.sha256((prefix / 'lib' / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('OpenSubdiv changed after acceptance; revalidate it.')
    if args.cycles:
        proof_path = CACHE / 'tbb-probe/validation.json'
        if not proof_path.exists():
            raise SystemExit('Build and validate browser oneTBB before enabling CPU Cycles.')
        proof = json.loads(proof_path.read_text())
        if (proof.get('library_sha256') != hashlib.sha256((prefix / 'lib/libtbb.a').read_bytes()).hexdigest()
            or proof.get('probe_sha256') != hashlib.sha256((ROOT / 'tests/tbb_runtime_probe.cc').read_bytes()).hexdigest()):
            raise SystemExit('Browser oneTBB changed after acceptance; revalidate it before enabling Cycles.')
        graphics += ["-DWITH_CYCLES_OSL=OFF", "-DWITH_CYCLES_EMBREE=OFF",
                     "-DWITH_CYCLES_PATH_GUIDING=OFF", "-DWITH_CYCLES_NATIVE_ONLY=OFF",
                     "-DCXX_HAS_SSE42=FALSE", "-DCXX_HAS_AVX2=FALSE", "-DCXX_HAS_F16C=FALSE"]
        graphics += ["-DWITH_CYCLES_DEVICE_" + backend + "=OFF" for backend in
                     ("CUDA", "OPTIX", "HIP", "HIPRT", "METAL", "ONEAPI")]
    if args.webgpu:
        graphics += ["-DWITH_WEBGPU_BACKEND=ON", "-DBROWSER_DAWN_SOURCE_DIR=" + str(CACHE / "graphics-src/dawn"),
                    "-DBROWSER_TINT_BUILD_DIR=" + str(CACHE / "deps-build/tint-threaded")]
    if args.editor:
        graphics += ["-DWITH_HEADLESS=OFF", "-DWITH_GHOST_WEB=ON", "-DWITH_GHOST_WEBGPU_CONTEXT=ON"]
    run("emcmake", "cmake", "-S", source, "-B", build, "-G", "Ninja",
        "-DBROWSER_RUNTIME_PREFIX=" + str(prefix),
        "-DBROWSER_HOST_PYTHON=" + str(CACHE / "deps-build/python-host/python"),
        "-DBLENDER_HOST_SHADER_TOOL=" + str(shader_tool),
        # Native Python extension loading exports every symbol on Unix. WASM
        # uses statically linked modules; exporting the entire Blender binary
        # exceeds browser engine limits and needlessly inflates its launcher.
        "-DPYTHON_LINKFLAGS=",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=OFF",
        "-C", ROOT / "cmake/browser-core.cmake",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_PREFIX_PATH=" + str(prefix),
        "-DCMAKE_FIND_ROOT_PATH=" + str(prefix),
        "-DCMAKE_PROJECT_INCLUDE=" + str(ROOT / "cmake/threaded-emscripten.cmake"),
        "-DCMAKE_C_FLAGS=" + flags, "-DCMAKE_CXX_FLAGS=" + flags,
        "-DCMAKE_EXE_LINKER_FLAGS=" + link, *graphics, env=env)
    if not args.configure_only and args.objects_only:
        link_prerequisites(build, env)
    elif not args.configure_only:
        run("cmake", "--build", build, "--target", "bf_gpu" if args.gpu_library_only else "blender", "--parallel", "4", env=env)
