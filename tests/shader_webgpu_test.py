#!/usr/bin/env python3
"""Dispatch translated Blender GPU math and validate numeric WebGPU readback."""
import hashlib
import json
import math
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
shader = ROOT / '.cache/shader-compiler-tests/blender-matrix.wgsl'
proof = json.loads((shader.parent / 'translation-validation.json').read_text())
assert proof.get(shader.name) == hashlib.sha256(shader.read_bytes()).hexdigest(), 'Shader differs from validated translation'
wgsl = shader.read_text()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get(
        'CHROMIUM_PATH', '/usr/lib/chromium/chromium'), args=[
        '--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
        '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    page = browser.new_page()
    # localhost is a browser secure context; use an intercepted document solely
    # for this internal test. No user-facing deployment is created.
    page.route('http://localhost/shader-test', lambda route: route.fulfill(
        status=200, content_type='text/html', body='<html><body>GPU acceptance</body></html>'))
    page.goto('http://localhost/shader-test')
    result = page.evaluate('''async (code) => {
      if (!navigator.gpu) throw new Error('WebGPU unavailable');
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) throw new Error('WebGPU adapter unavailable');
      const device = await adapter.requestDevice();
      const errors = [];
      device.addEventListener('uncapturederror', event => errors.push(event.error.message));
      device.pushErrorScope('validation');
      const shader = device.createShaderModule({code});
      const info = await shader.getCompilationInfo();
      const diagnostics = info.messages.filter(m => m.type === 'error').map(m => m.message);
      if (diagnostics.length) throw new Error(diagnostics.join('\\n'));
      const pipeline = await device.createComputePipelineAsync({layout:'auto', compute:{module:shader}});
      const output = device.createBuffer({size:80, usage:GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC});
      const readback = device.createBuffer({size:80, usage:GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
      const input = device.createBuffer({size:64, usage:GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST});
      const bindings = device.createBindGroup({layout:pipeline.getBindGroupLayout(0),
        entries:[{binding:0, resource:{buffer:output}}, {binding:1, resource:{buffer:input}}]});
      const results = [];
      for (const matrix of [[2,0,0,0, 1,3,0,0, 0,0,4,0, 5,6,7,1], Array(16).fill(0)]) {
        device.queue.writeBuffer(input, 0, new Float32Array(matrix));
        const encoder = device.createCommandEncoder();
        const pass = encoder.beginComputePass();
        pass.setPipeline(pipeline); pass.setBindGroup(0, bindings); pass.dispatchWorkgroups(1); pass.end();
        encoder.copyBufferToBuffer(output,0,readback,0,80);
        device.queue.submit([encoder.finish()]);
        await readback.mapAsync(GPUMapMode.READ);
        results.push(Array.from(new Float32Array(readback.getMappedRange())));
        readback.unmap();
      }
      const validation = await device.popErrorScope();
      if (validation) errors.push(validation.message);
      output.destroy(); readback.destroy(); input.destroy(); device.destroy();
      return {results, errors, adapter:adapter.info.description};
    }''', wgsl)
    assert not result['errors'], result
    expected = [0.5,0,0,0, -1/6,1/3,0,0, 0,0,0.25,0, -1.5,-2,-1.75,1, 1,1,1,1]
    assert len(result['results']) == 2, result
    for actual, wanted in zip(result['results'], [expected, [0]*20]):
        assert len(actual) == 20, result
        assert all(math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)
                   for a, b in zip(actual, wanted)), result
    browser.close()
print('PASS: translated Blender matrix shader executed through WebGPU; inverse and singular-matrix readbacks verified.')
