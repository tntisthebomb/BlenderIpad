#!/usr/bin/env python3
"""Build the SDK-matched Tint translator with Blender's shared SPIR-V ABI."""
import subprocess
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from setup_browser import CACHE, ROOT, LOCK, toolchain, run
from build_browser_deps import fetch

def pinned_git(name):
    spec = LOCK['webgpu_toolchain'][name]
    source = CACHE / 'graphics-src' / name
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'init', source)
        run('git', '-C', source, 'fetch', '--depth', '1', spec['repository'], spec['commit'])
        run('git', '-C', source, 'checkout', '--detach', 'FETCH_HEAD')
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != spec['commit']:
        raise SystemExit(name + ': source commit differs from the pin')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True):
        raise SystemExit(name + ': preserve local changes before building')
    return source

def patched_source(source, relative, patch_name):
    """Apply a guarded translator correction without editing the checkout."""
    build = CACHE / 'tint-patched-source'
    build.mkdir(exist_ok=True)
    destination = build / Path(relative).name
    stamp = build / (Path(relative).stem + '.json')
    previous = json.loads(stamp.read_text()) if stamp.exists() else {}
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != previous.get('output_sha256'):
        raise SystemExit('Preserve unrecognized edits to the patched Tint source before rebuilding.')
    with tempfile.TemporaryDirectory(dir=CACHE) as temporary:
        temporary = Path(temporary)
        patch = ROOT / 'patches' / patch_name
        paths = {line[6:] for line in patch.read_text().splitlines()
                 if line.startswith('+++ b/')}
        for path in paths:
            target = temporary / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, target)
        run('git', 'apply', '--check', patch, cwd=temporary)
        run('git', 'apply', patch, cwd=temporary)
        output = (temporary / relative).read_bytes()
    if not destination.exists() or destination.read_bytes() != output:
        destination.write_bytes(output)
    stamp.write_text(json.dumps({'source_commit': LOCK['webgpu_toolchain']['dawn']['commit'],
        'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(output).hexdigest()}, indent=2) + '\n')
    return destination

if __name__ == '__main__':
    env = toolchain()
    run(CACHE / 'python/bin/python', '-m', 'pip', 'install', '--cache-dir', CACHE / 'pip',
        'Jinja2==3.1.6', 'MarkupSafe==3.0.3')
    packages = subprocess.check_output([str(CACHE / 'python/bin/python'), '-c',
        'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip()
    source, abseil = pinned_git('dawn'), pinned_git('abseil')
    atomics = patched_source(source, 'src/tint/lang/spirv/reader/lower/atomics.cc',
                             'tint-atomics-composite.patch')
    intrinsic_source = patched_source(source, 'src/tint/lang/spirv/intrinsic/data.cc',
                                      'tint-image-overloads.patch')
    patched_source(source, 'src/tint/lang/spirv/spirv.def', 'tint-image-overloads.patch')
    spirv, headers = fetch('spirv-tools'), fetch('spirv-headers')
    build = CACHE / 'deps-build/tint-threaded'
    prefix = CACHE / 'wasm-threaded-sysroot'
    build.mkdir(parents=True, exist_ok=True)
    (build / 'package.json').write_text('{"type":"commonjs"}\n')
    options = dict(DAWN_BUILD_SAMPLES='OFF', DAWN_BUILD_TESTS='OFF',
                   DAWN_BUILD_NODE_BINDINGS='OFF', DAWN_BUILD_BENCHMARKS='OFF',
                   DAWN_BUILD_PROTOBUF='OFF', DAWN_FETCH_DEPENDENCIES='OFF',
                   DAWN_BUILD_MONOLITHIC_LIBRARY='OFF', DAWN_WERROR='OFF',
                   TINT_BUILD_SPV_READER='ON', TINT_BUILD_WGSL_READER='ON',
                   TINT_BUILD_WGSL_WRITER='ON', TINT_BUILD_CMD_TOOLS='OFF',
                   TINT_BUILD_TESTS='OFF', TINT_BUILD_IR_BINARY='OFF',
                   TINT_BUILD_GLSL_VALIDATOR='OFF', TINT_BUILD_FUZZERS='OFF',
                   TINT_BUILD_BENCHMARKS='OFF', TINT_ENABLE_IR_VALIDATION='ON',
                   ABSL_BUILD_TESTING='OFF')
    for backend in ['D3D11', 'D3D12', 'METAL', 'NULL', 'WEBGPU_ON_WEBGPU', 'DESKTOP_GL', 'OPENGLES', 'VULKAN', 'SWIFTSHADER']:
        options['DAWN_ENABLE_' + backend] = 'OFF'
    for writer in ['GLSL', 'HLSL', 'MSL', 'SPV']:
        options['TINT_BUILD_' + writer + '_WRITER'] = 'OFF'
    run('emcmake', 'cmake', '-S', source, '-B', build, '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF',
        '-DCMAKE_POSITION_INDEPENDENT_CODE=OFF', '-DCMAKE_CXX_STANDARD=20',
        '-DCMAKE_C_FLAGS=-pthread -fexceptions', '-DCMAKE_CXX_FLAGS=-pthread -fexceptions',
        '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_FIND_ROOT_PATH=' + str(prefix),
        '-DCMAKE_PROJECT_INCLUDE=' + str(ROOT / 'cmake/tint-emscripten.cmake'),
        '-DDAWN_JINJA2_DIR=' + packages, '-DDAWN_MARKUPSAFE_DIR=' + packages,
        '-DBLENDER_SHADER_PROBE_SOURCE=' + str(ROOT / 'tests/shader_translation_probe.cc'),
        '-DBLENDER_TINT_ATOMICS_SOURCE=' + str(atomics),
        '-DBLENDER_TINT_INTRINSIC_SOURCE=' + str(intrinsic_source),
        '-DCMAKE_EXE_LINKER_FLAGS=-pthread -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0 -sSTACK_SIZE=8388608',
        '-DDAWN_ABSEIL_DIR=' + str(abseil), '-DDAWN_SPIRV_TOOLS_DIR=' + str(spirv),
        '-DDAWN_SPIRV_HEADERS_DIR=' + str(headers),
        '-Dspirv-tools_BINARY_DIR=' + str(CACHE / 'deps-build/shaderc-threaded/third_party/spirv-tools'),
        *['-D' + key + '=' + value for key, value in options.items()], env=env)
    run('cmake', '--build', build, '--target', 'tint_api', '--parallel', '4', env=env)
    print('Tint library built; shader translation and WebGPU execution need separate acceptance checks.')
