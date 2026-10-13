#!/usr/bin/env python3
"""Verify whole composite loads/stores mixed with atomic accesses on the GPU."""
import hashlib
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
shader = ROOT / '.cache/shader-compiler-tests/atomic-composite.wgsl'
proof = json.loads((shader.parent / 'translation-validation.json').read_text())
assert proof.get(shader.name) == hashlib.sha256(shader.read_bytes()).hexdigest()
with sync_playwright() as playwright:
    executable = os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium')
    environment = dict(os.environ)
    driver = Path(executable).resolve().parent / 'vk_swiftshader_icd.json'
    if driver.exists(): environment['VK_ICD_FILENAMES'] = str(driver)
    browser = playwright.chromium.launch(executable_path=executable, env=environment,
        args=['--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
              '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    try:
        page = browser.new_page()
        page.route('http://localhost/atomic-test', lambda route: route.fulfill(
            content_type='text/html', body='<html><body>Atomic acceptance</body></html>'))
        page.goto('http://localhost/atomic-test')
        result = page.evaluate('''async code => {
          const adapter = await navigator.gpu.requestAdapter();
          const device = await adapter.requestDevice();
          device.pushErrorScope('validation');
          const module = device.createShaderModule({code});
          const diagnostics = (await module.getCompilationInfo()).messages.filter(m => m.type === 'error');
          if (diagnostics.length) throw new Error(diagnostics.map(m=>m.message).join('\\n'));
          const pipeline = await device.createComputePipelineAsync({layout:'auto',compute:{module}});
          const input = device.createBuffer({size:40,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST});
          const output = device.createBuffer({size:40,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});
          const readback = device.createBuffer({size:40,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
          device.queue.writeBuffer(input,0,new Uint32Array([11,13,5,17,23,29,31,37,41,43]));
          const group = device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[
            {binding:0,resource:{buffer:input}},{binding:1,resource:{buffer:output}}]});
          const encoder = device.createCommandEncoder();
          const pass = encoder.beginComputePass();
          pass.setPipeline(pipeline); pass.setBindGroup(0,group); pass.dispatchWorkgroups(1); pass.end();
          encoder.copyBufferToBuffer(output,0,readback,0,40);
          device.queue.submit([encoder.finish()]);
          await readback.mapAsync(GPUMapMode.READ);
          const values = Array.from(new Uint32Array(readback.getMappedRange()));
          readback.unmap();
          const error = await device.popErrorScope();
          input.destroy(); output.destroy(); readback.destroy(); device.destroy();
          return {values,error:error?.message};
        }''', shader.read_text())
        assert not result.get('error'), result
        assert result['values'] == [11,13,7,17,11,13,10,17,41,47], result
    finally:
        browser.close()
print('PASS: atomic structure/vector/array loads and stores preserve GPU values.')
