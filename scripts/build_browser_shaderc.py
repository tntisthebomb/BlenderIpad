#!/usr/bin/env python3
"""Build Blender's pinned GLSL/SPIR-V toolchain, a WebGPU prerequisite."""
from setup_browser import CACHE, ROOT, toolchain, run
from build_browser_deps import fetch

if __name__ == '__main__':
    env = toolchain()
    source = fetch('shaderc')
    glslang = fetch('shaderc-glslang')
    headers = fetch('spirv-headers')
    spirv = fetch('spirv-tools')
    prefix = CACHE / 'wasm-threaded-sysroot'
    build = CACHE / 'deps-build/shaderc-threaded'
    build.mkdir(parents=True, exist_ok=True)
    (build / 'package.json').write_text('{"type":"commonjs"}\n')
    run('emcmake', 'cmake', '-S', source, '-B', build, '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF',
        '-DCMAKE_POSITION_INDEPENDENT_CODE=OFF',
        '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
        '-DCMAKE_C_FLAGS=-pthread -fexceptions',
        '-DCMAKE_CXX_FLAGS=-pthread -fexceptions',
        '-DCMAKE_PROJECT_INCLUDE=' + str(ROOT / 'cmake/threaded-emscripten.cmake'),
        '-DCMAKE_EXE_LINKER_FLAGS=-pthread -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0 -sSTACK_SIZE=4194304',
        '-DSHADERC_SPIRV_TOOLS_DIR=' + str(spirv),
        '-DSHADERC_SPIRV_HEADERS_DIR=' + str(headers),
        '-DSHADERC_GLSLANG_DIR=' + str(glslang),
        '-DSPIRV-Headers_SOURCE_DIR=' + str(headers),
        '-DSHADERC_SKIP_TESTS=ON', '-DSHADERC_SKIP_EXAMPLES=ON',
        '-DSHADERC_SKIP_EXECUTABLES=ON', '-DSPIRV_SKIP_TESTS=ON',
        '-DSPIRV_SKIP_EXECUTABLES=ON', '-DSPIRV_TOOLS_BUILD_STATIC=ON',
        '-DENABLE_GLSLANG_BINARIES=OFF', '-DGLSLANG_TESTS=OFF',
        '-DGLSLANG_ENABLE_INSTALL=ON', env=env)
    run('cmake', '--build', build, '--parallel', '4', env=env)
    run('cmake', '--install', build, env=env)
    print('Compiled shaderc/SPIR-V libraries; compiler acceptance and WebGPU integration are separate checks.')
