#!/usr/bin/env python3
"""Execute translated switch/volume regressions on an actual WebGPU device."""
import hashlib
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / '.cache/shader-compiler-tests'


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(directory)))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium'),
            args=['--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
                  '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        context = browser.new_context()
        page = context.new_page()
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        sources = {name: (directory / (name + '.wgsl')).read_text()
                   for name in ('switch-fallthrough', 'switch-phi', 'volume-query')}
        context.set_offline(True)
        results = page.evaluate('''async sources => {
          const adapter = await navigator.gpu.requestAdapter();
          if (!adapter) throw Error('WebGPU adapter unavailable');
          const device = await adapter.requestDevice();
          const errors = [];
          device.addEventListener('uncapturederror', event => errors.push(event.error.message));
          const results = {};
          for (const [name, code] of Object.entries(sources)) {
            device.pushErrorScope('validation');
            const shader = device.createShaderModule({code});
            const info = await shader.getCompilationInfo();
            const failures = info.messages.filter(message => message.type === 'error');
            if (failures.length) throw Error(JSON.stringify(failures));
            const pipeline = await device.createComputePipelineAsync({
              layout: 'auto', compute: {module: shader, entryPoint: 'main'}});
            const size = name === 'volume-query' ? 16 : 24;
            const output = device.createBuffer({size,
              usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC});
            const read = device.createBuffer({size,
              usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
            const entries = [{binding: 0, resource: {buffer: output}}];
            if (name === 'volume-query') {
              const texture = device.createTexture({size: [2, 3, 4], dimension: '3d',
                format: 'rgba8unorm', usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST});
              const texels = new Uint8Array(2 * 3 * 4 * 4);
              texels[92] = 42;
              device.queue.writeTexture({texture}, texels, {bytesPerRow: 8, rowsPerImage: 3}, [2, 3, 4]);
              entries.push({binding: 1, resource: texture.createView()});
              entries.push({binding: 129, resource: device.createSampler()});
            }
            const group = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries});
            const encoder = device.createCommandEncoder();
            const pass = encoder.beginComputePass();
            pass.setPipeline(pipeline); pass.setBindGroup(0, group);
            pass.dispatchWorkgroups(name === 'volume-query' ? 1 : 6); pass.end();
            encoder.copyBufferToBuffer(output, 0, read, 0, size);
            device.queue.submit([encoder.finish()]);
            await read.mapAsync(GPUMapMode.READ);
            results[name] = Array.from(new Int32Array(read.getMappedRange()));
            read.unmap();
            const error = await device.popErrorScope();
            if (error) throw Error(error.message);
          }
          if (errors.length) throw Error(JSON.stringify(errors));
          device.destroy();
          return results;
        }''', sources)
        assert results['switch-fallthrough'] == [9, 3, 13, 8, -5, -5], results
        assert results['switch-phi'] == [9, 3, 13, 8, -5, -5], results
        assert results['volume-query'] == [2, 3, 4, 42], results
        (directory / 'semantics-validation.json').write_text(json.dumps({
            'results': results,
            'wgsl_sha256': {name: hashlib.sha256(code.encode()).hexdigest()
                            for name, code in sources.items()}}, indent=2) + '\n')
        browser.close()
    print('PASS: real WebGPU switch fallthrough, nested control flow, 3D dimensions and texel fetch offline.')
finally:
    server.shutdown()
    server.server_close()
