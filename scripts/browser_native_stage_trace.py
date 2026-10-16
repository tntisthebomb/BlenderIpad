"""Guarded diagnostics for the existing emdawnwebgpu C/JS bridge."""

def instrument_native_stages(js):
 def replace(old,new):
  nonlocal js
  if js.count(old)!=1:raise ValueError('Unrecognized browser bridge: '+old[:80])
  js=js.replace(old,new)
 marker='var _wgpuCommandEncoderFinish = (encoderPtr, descriptor) => {'
 helper='''// Bounded startup diagnostics; callbacks cannot change native API behavior.
var browserNativeTraceCount = 0;
var browserNativeTrace = (stage, status, detail) => {
  if (!Module["browserStartupTrace"] || browserNativeTraceCount++ >= 96) return;
  try { Module["onNativeStartupTrace"]?.(stage, status, String(detail ?? "").slice(0, 120)); } catch {}
};
'''
 replace(marker,helper+marker+'\n  browserNativeTrace("encoder-finish-enter", "in progress", encoderPtr >>> 0);')
 replace('''  var ptr = _emwgpuCreateCommandBuffer(0);
  WebGPU.Internals.jsObjectInsert(ptr, commandEncoder.finish());
  return ptr;''','''  browserNativeTrace("command-buffer-allocation", "in progress", encoderPtr >>> 0);
  var ptr = _emwgpuCreateCommandBuffer(0);
  browserNativeTrace("command-buffer-allocation", "call returned", ptr >>> 0);
  var commandBuffer = commandEncoder.finish();
  browserNativeTrace("command-buffer-registration", "in progress", ptr >>> 0);
  WebGPU.Internals.jsObjectInsert(ptr, commandBuffer);
  browserNativeTrace("command-buffer-registration", "call returned", ptr >>> 0);
  return ptr;''')
 replace('var _wgpuQueueSubmit = (queuePtr, commandCount, commands) => {',
         'var _wgpuQueueSubmit = (queuePtr, commandCount, commands) => {\n  browserNativeTrace("queue-submit-enter", "in progress", (queuePtr >>> 0) + " count=" + commandCount);')
 replace('''  var queue = WebGPU.getJsObject(queuePtr);
  var cmds = Array.from''','''  var queue = WebGPU.getJsObject(queuePtr);
  browserNativeTrace("queue-resolved", "call returned", queuePtr >>> 0);
  var cmds = Array.from''')
 replace('  queue.submit(cmds);','''  browserNativeTrace("submitted-command-buffers-resolved", "call returned", commandCount);
  queue.submit(cmds);
  browserNativeTrace("queue-submit-returned", "call returned", queuePtr >>> 0);''')
 replace('  WebGPU.Internals.jsObjectInsert(queuePtr, device.queue);','''  var queue = device.queue;
  try { Module["onBrowserGPUQueue"]?.(queue); } catch {}
  WebGPU.Internals.jsObjectInsert(queuePtr, queue);''')
 replace('  var context = canvas.getContext("webgpu");','''  var context = canvas.getContext("webgpu");
  try { Module["onBrowserGPUCanvas"]?.(context); } catch {}''')
 # A future source build already has this pre-run statement; older accepted
 # engines receive the equivalent guarded statement without changing WASM.
 if 'ENV["BLENDER_GPU_INIT_TRACE"]' not in js:
  replace('  ENV["XDG_CACHE_HOME"] = "/cache";',
          '  ENV["XDG_CACHE_HOME"] = "/cache";\n  if (Module["browserStartupTrace"]) ENV["BLENDER_GPU_INIT_TRACE"] = "1";')
 return js
