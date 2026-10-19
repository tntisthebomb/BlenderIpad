#!/usr/bin/env python3
"""Exercise Blender's actual compiled shader registry without GUI startup."""
import argparse
import shlex
import subprocess
from setup_browser import CACHE,ROOT,toolchain,run
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--webgpu',action='store_true')
    parser.add_argument('--gpu-runtime',action='store_true')
    options=parser.parse_args()
    if options.gpu_runtime:
        options.webgpu=True
    env=toolchain();core=CACHE/('blender-webgpu-build' if options.webgpu else 'blender-core-build')
    build=CACHE/('gpu-runtime-tests' if options.gpu_runtime else 'shader-registry-tests');build.mkdir(exist_ok=True)
    (build/'package.json').write_text('{"type":"commonjs"}\n')
    commands=subprocess.check_output(['ninja','-t','commands','bin/blender.js'],cwd=core,env=env,text=True).splitlines()
    compile=shlex.split(next(c for c in commands if c.endswith('/intern/gpu_shader_dependency.cc')))
    compile[compile.index('-o')+1]=str(build/'probe.o')
    compile[compile.index('-MF')+1]=str(build/'probe.d')
    compile[-1]=str(ROOT/('tests/gpu_runtime_probe.cc' if options.gpu_runtime else 'tests/shader_registry_probe.cc'))
    run(*compile,cwd=core,env=env)
    link=shlex.split(next(c for c in commands if ' -o bin/blender.js ' in c))
    link=link[link.index('&&')+1:link.index('&&',link.index('&&')+1)]
    link=[a for a in link if not a.startswith('source/creator/CMakeFiles/blender.dir/') and (options.gpu_runtime or not a.startswith('-sASYNCIFY'))]
    if options.gpu_runtime:
        link.remove('-sNODERAWFS=1')
        link[link.index('-sENVIRONMENT=node')]='-sENVIRONMENT=web,worker'
        link[link.index('--pre-js')+1]=str(ROOT/'native/browser/core_browser_env.js')
        link += ['-sMODULARIZE=1','-sEXPORT_NAME=createGPUProbe']
    link[link.index('-o')+1]=str(build/'shader-registry.js')
    link += [str(build/'probe.o')]
    run(*link,cwd=core,env=env)
    if options.gpu_runtime:
        (build/'index.html').write_text('''<!doctype html><html><body>
<script src="shader-registry.js"></script><script>
(async()=>{
  const adapter=await navigator.gpu.requestAdapter();
  const device=await adapter.requestDevice({requiredFeatures:['depth32float-stencil8']});
  device.addEventListener('uncapturederror',event=>document.body.dataset.error=event.error.message);
  const module=await createGPUProbe({preinitializedWebGPUDevice:device,noInitialRun:true,
    onAbort:message=>document.body.dataset.error=String(message)});
  await module.runBlenderMain([]);
})().catch(error=>document.body.dataset.error=String(error));
</script></body></html>''')
    else:
        run(CACHE/'emsdk/node/22.16.0_64bit/bin/node',build/'shader-registry.js',env=env)
