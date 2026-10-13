#!/usr/bin/env python3
"""Verify quiet NaN bits and nearest integer ID texture samples on the GPU."""
import hashlib
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
shader = ROOT / '.cache/shader-compiler-tests/portable-math.wgsl'
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
        page.route('http://localhost/portable-test', lambda route: route.fulfill(
            content_type='text/html', body='<html><body>Atomic acceptance</body></html>'))
        page.goto('http://localhost/portable-test')
        result = page.evaluate('''async code => {
          const adapter = await navigator.gpu.requestAdapter();
          const device = await adapter.requestDevice();
          device.pushErrorScope('validation');
          const module = device.createShaderModule({code});
          const diagnostics = (await module.getCompilationInfo()).messages.filter(m => m.type === 'error');
          if (diagnostics.length) throw new Error(diagnostics.map(m=>m.message).join('\\n'));
          const pipeline = await device.createComputePipelineAsync({layout:'auto',compute:{module}});
          const input = device.createTexture({size:[4,4],format:'r32uint',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST});
          const output = device.createBuffer({size:32,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});
          const readback = device.createBuffer({size:32,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
          device.queue.writeTexture({texture:input},new Uint32Array(Array.from({length:16},(_,i)=>i+3)),{bytesPerRow:16,rowsPerImage:4},[4,4]);
          const group = device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[
            {binding:0,resource:input.createView()},
            {binding:1,resource:{buffer:output}},
            {binding:128,resource:device.createSampler()}]});
          const encoder = device.createCommandEncoder();
          const pass = encoder.beginComputePass();
          pass.setPipeline(pipeline); pass.setBindGroup(0,group); pass.dispatchWorkgroups(1); pass.end();
          encoder.copyBufferToBuffer(output,0,readback,0,32);
          device.queue.submit([encoder.finish()]);
          await readback.mapAsync(GPUMapMode.READ);
          const values = Array.from(new Uint32Array(readback.getMappedRange()));
          readback.unmap();
          const error = await device.popErrorScope();
          input.destroy(); output.destroy(); readback.destroy(); device.destroy();
          return {values,error:error?.message};
        }''', shader.read_text())
        assert not result.get('error'), result
        assert result['values'] == [0x7FC00000,1,3,8,18,18,10,15], result
    finally:
        browser.close()
print('PASS: quiet NaN bit pattern and nearest integer ID sampling, including clamped edges, preserve GPU values.')
