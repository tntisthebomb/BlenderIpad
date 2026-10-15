#!/usr/bin/env python3
"""Execute the WASM shader compiler against Blender's actual matrix library."""
from setup_browser import CACHE, ROOT, toolchain, prepare_source, run

if __name__ == '__main__':
    env = toolchain()
    source = prepare_source()
    from build_blender_core import host_shader_tool
    shader_tool = host_shader_tool(source)
    prefix = CACHE / 'wasm-threaded-sysroot'
    build = CACHE / 'shader-compiler-tests'
    build.mkdir(exist_ok=True)
    (build / 'package.json').write_text('{"type":"commonjs"}\n')
    gpu = source / 'source/blender/gpu'
    generated = build / 'generated'
    generated.mkdir(exist_ok=True)
    for name in ['gpu_shader_math_matrix_lib.glsl', 'gpu_shader_utildefines_lib.glsl']:
        base = generated / 'common' / name
        base.parent.mkdir(exist_ok=True)
        run(shader_tool, gpu / 'shaders/common' / name,
            str(base) + '.tmp', str(base) + '.hh', str(base) + '.info', str(base) + '.d',
            gpu, gpu / 'intern', gpu / 'shaders', gpu / 'shaders/common',
            gpu / 'shaders/infos', gpu / 'shaders/material', gpu / 'vulkan/shaders', env=env)
    run('em++', ROOT / 'tests/shader_compiler_probe.cc', '-std=c++20', '-O1',
        '-pthread', '-fexceptions', '-I' + str(prefix / 'include'),
        prefix / 'lib/libshaderc_combined.a', '-sNODERAWFS=1',
        '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=134217728',
        '-sASSERTIONS=2', '-sDISABLE_EXCEPTION_CATCHING=0',
        '-sSTACK_SIZE=8388608', '-sDEFAULT_PTHREAD_STACK_SIZE=2097152',
        '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=2', '-sPTHREAD_POOL_SIZE_STRICT=0',
        '-sEXIT_RUNTIME=1', '-o', build / 'shader-compiler.js', env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', build / 'shader-compiler.js',
        gpu / 'shaders', generated,
        build / 'blender-matrix.spv', env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', build / 'shader-compiler.js',
        gpu / 'shaders', generated, build / 'atomic-composite.spv',
        ROOT / 'tests/shader_atomic_composite.comp', env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', build / 'shader-compiler.js',
        gpu / 'shaders', generated, build / 'portable-math.spv',
        ROOT / 'tests/shader_portable_math.comp', env=env)
    for name in ('switch-fallthrough', 'switch-phi', 'volume-query', 'readwrite-texture', 'atomic-image', 'zbin-range', 'unorm16-image', 'buffer-image'):
        run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', build / 'shader-compiler.js',
            gpu / 'shaders', generated, build / (name + '.spv'),
            ROOT / ('tests/shader_' + name.replace('-', '_') + '.comp'), env=env)
    run(CACHE / 'emsdk/node/22.16.0_64bit/bin/node', build / 'shader-compiler.js',
        gpu / 'shaders', generated, build / 'interface-names.spv',
        ROOT / 'tests/shader_interface_names.vert', '0', env=env)
