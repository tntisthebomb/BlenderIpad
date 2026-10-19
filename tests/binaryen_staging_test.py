"""Compare real Binaryen optimization and actual Asyncify unwind/rewind."""
import os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from low_memory_wasm_opt import stage_link
root=ROOT;tool=root/'.cache/emsdk/upstream/bin/wasm-opt'
folder=root/'.cache/binaryen-staging-tests';folder.mkdir(exist_ok=True)
source=folder/'async.wat'
source.write_text('''(module
(import "env" "emscripten_sleep" (func $sleep (param i32)))
(memory (export "memory") 1)
(func $run (export "run") (param $n i32) (result i32)
 local.get $n call $sleep
 local.get $n i32.const 3 i32.mul i32.const 7 i32.add))''')
base=['--strip-target-features','--post-emscripten','-O2','--low-memory-unused',
      '--asyncify','--pass-arg=asyncify-asserts','--pass-arg=asyncify-imports@env.emscripten_sleep',
      '--zero-filled-memory','--pass-arg=directize-initial-contents-immutable',
      '--one-caller-inline-max-function-size=0','-g','--mvp-features','--enable-threads',
      '--enable-bulk-memory','--enable-multivalue','--enable-reference-types','--enable-simd']
os.environ['BLENDER_BINARYEN_PREFIX_CACHE']=str(folder/'prefix-cache')
os.environ['BLENDER_BINARYEN_STAGE_LOG']=str(folder/'stages.jsonl')
subprocess.run([str(tool),*base,str(source),'-o',str(folder/'original.wasm')],check=True)
stage_link(tool,[*base,str(source),'-o',str(folder/'staged.wasm')])
assert (folder/'original.wasm').read_bytes()==(folder/'staged.wasm').read_bytes(), 'Small-module pass replay differs from the pinned optimizer'
stage_link(tool,[*base,str(source),'-o',str(folder/'cached.wasm')])
assert (folder/'cached.wasm').read_bytes()==(folder/'original.wasm').read_bytes()
assert 'prefix-cache-hit' in (folder/'stages.jsonl').read_text()
script=folder/'check.mjs'
script.write_text('''import fs from 'node:fs';
import assert from 'node:assert/strict';
for(const path of process.argv.slice(2)){
  let instance,phase='sleep',calls=0;
  const result=await WebAssembly.instantiate(fs.readFileSync(path),{env:{emscripten_sleep(){
    calls++;
    if(phase==='sleep')instance.exports.asyncify_start_unwind(1024);
    else instance.exports.asyncify_stop_rewind();
  }}});
  instance=result.instance;
  const memory=new Uint32Array(instance.exports.memory.buffer);
  memory[256]=2048;memory[257]=65536;
  instance.exports.run(5);
  instance.exports.asyncify_stop_unwind();
  phase='rewind';instance.exports.asyncify_start_rewind(1024);
  assert.equal(instance.exports.run(5),22);
  assert.equal(calls,2);
  console.log('PASS: actual Asyncify unwind/rewind returns 22:',path);
}''')
subprocess.run([str(root/'.cache/emsdk/node/22.16.0_64bit/bin/node'),str(script),
    str(folder/'original.wasm'),str(folder/'staged.wasm'),str(folder/'cached.wasm')],check=True)
