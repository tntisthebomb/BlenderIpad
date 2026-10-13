#!/usr/bin/env python3
"""Exercise Blender's actual compiled shader registry without GUI startup."""
import shlex
import subprocess
from setup_browser import CACHE,ROOT,toolchain,run
if __name__=='__main__':
    env=toolchain();core=CACHE/'blender-webgpu-build'
    build=CACHE/'shader-registry-tests';build.mkdir(exist_ok=True)
    (build/'package.json').write_text('{"type":"commonjs"}\n')
    commands=subprocess.check_output(['ninja','-t','commands','bin/blender.js'],cwd=core,env=env,text=True).splitlines()
    compile=shlex.split(next(c for c in commands if c.endswith('/intern/gpu_shader_dependency.cc')))
    compile[compile.index('-o')+1]=str(build/'probe.o')
    compile[compile.index('-MF')+1]=str(build/'probe.d')
    compile[-1]=str(ROOT/'tests/shader_registry_probe.cc')
    run(*compile,cwd=core,env=env)
    link=shlex.split(next(c for c in commands if ' -o bin/blender.js ' in c))
    link=link[link.index('&&')+1:link.index('&&',link.index('&&')+1)]
    link=[a for a in link if not a.startswith('source/creator/CMakeFiles/blender.dir/') and not a.startswith('-sASYNCIFY')]
    link[link.index('-o')+1]=str(build/'shader-registry.js')
    link += [str(build/'probe.o')]
    run(*link,cwd=core,env=env)
    run(CACHE/'emsdk/node/22.16.0_64bit/bin/node',build/'shader-registry.js',env=env)
