#!/usr/bin/env python3
"""Compile the production buffer pool for actual GPU ordering/lifetime checks."""
from setup_browser import ROOT, CACHE, toolchain, run
if __name__ == '__main__':
    env = toolchain()
    out = CACHE / 'frame-buffer-pool-probe'
    out.mkdir(exist_ok=True)
    run('em++', ROOT / 'native/browser/frame_buffer_pool_probe.cc', '-O2',
        '--use-port=emdawnwebgpu', '-sASSERTIONS=2', '-sENVIRONMENT=web',
        '-sMODULARIZE=1', '-sEXPORT_NAME=createPoolProbe', '-sEXIT_RUNTIME=0',
        '-o', out / 'probe.js', env=env)
    (out / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><body>
<script src="probe.js"></script><script>
(async()=>{
  const adapter=await navigator.gpu.requestAdapter();
  const device=await adapter.requestDevice();
  device.addEventListener('uncapturederror',e=>document.body.dataset.error=e.error.message);
  await createPoolProbe({preinitializedWebGPUDevice:device,
    onAbort:message=>document.body.dataset.error=String(message)});
})().catch(error=>document.body.dataset.error=String(error));
</script></body>''')
