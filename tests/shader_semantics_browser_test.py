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
                   for name in ('switch-fallthrough', 'switch-phi', 'volume-query',
                                'readwrite-texture', 'atomic-image', 'zbin-range', 'interface-names')}
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
            if (name === 'interface-names') {
              const fragment = device.createShaderModule({code: `
                struct Inputs { @location(0) first:vec3f, @location(1) second:vec3f,
                  @location(2) position:vec4f }
                @fragment fn main(input:Inputs)->@location(0) vec4f {
                  return vec4f(input.first.x,input.second.y*0.5,input.position.z*0.25,1);
                }`});
              const pipeline = await device.createRenderPipelineAsync({layout:'auto',
                vertex:{module:shader,entryPoint:'main',buffers:[{arrayStride:12,
                  attributes:[{shaderLocation:0,offset:0,format:'float32x3'}]}]},
                fragment:{module:fragment,entryPoint:'main',targets:[{format:'rgba8unorm'}]}});
              const vertices=device.createBuffer({size:36,
                usage:GPUBufferUsage.VERTEX|GPUBufferUsage.COPY_DST});
              device.queue.writeBuffer(vertices,0,new Float32Array([-1,-1,0,3,-1,0,-1,3,0]));
              const texture=device.createTexture({size:[1,1],format:'rgba8unorm',
                usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
              const read=device.createBuffer({size:256,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
              const encoder=device.createCommandEncoder();
              const pass=encoder.beginRenderPass({colorAttachments:[{view:texture.createView(),
                loadOp:'clear',storeOp:'store',clearValue:[0,0,0,0]}]});
              pass.setPipeline(pipeline);pass.setVertexBuffer(0,vertices);pass.draw(3);pass.end();
              encoder.copyTextureToBuffer({texture},{buffer:read,bytesPerRow:256},[1,1,1]);
              device.queue.submit([encoder.finish()]);await read.mapAsync(GPUMapMode.READ);
              results[name]=Array.from(new Uint8Array(read.getMappedRange())).slice(0,4);read.unmap();
              const error=await device.popErrorScope();if(error)throw Error(error.message);
              continue;
            }
            const pipeline = await device.createComputePipelineAsync({
              layout: 'auto', compute: {module: shader, entryPoint: 'main'}});
            const size = name === 'zbin-range' ? 16384 : name === 'atomic-image' ? 272 :
              name.endsWith('texture') || name === 'volume-query' ? 16 : 24;
            const output = device.createBuffer({size,
              usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST});
            if (name === 'atomic-image') {
              device.queue.writeBuffer(output, 0, new Uint32Array([4, 1, 1, 64, 0xffffffff, 0]));
            }
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
            if (name === 'readwrite-texture') {
              const texture = device.createTexture({size: [1, 1], format: 'r32uint',
                usage: GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.COPY_DST});
              device.queue.writeTexture({texture}, new Uint32Array([3]), {bytesPerRow: 4}, [1, 1]);
              entries.push({binding: 1, resource: texture.createView()});
            }
            const group = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries});
            const encoder = device.createCommandEncoder();
            const pass = encoder.beginComputePass();
            pass.setPipeline(pipeline); pass.setBindGroup(0, group);
            pass.dispatchWorkgroups(name === 'atomic-image' ? 16 :
              name === 'zbin-range' || size === 16 ? 1 : 6); pass.end();
            if (name === 'atomic-image') {
              const texture = device.createTexture({size: [4, 1], format: 'r32uint',
                usage: GPUTextureUsage.COPY_DST | GPUTextureUsage.COPY_SRC});
              encoder.copyBufferToTexture({buffer: output, offset: 16, bytesPerRow: 256,
                rowsPerImage: 1}, {texture}, [4, 1, 1]);
              encoder.copyTextureToBuffer({texture}, {buffer: read, bytesPerRow: 256,
                rowsPerImage: 1}, [4, 1, 1]);
            } else encoder.copyBufferToBuffer(output, 0, read, 0, size);
            device.queue.submit([encoder.finish()]);
            await read.mapAsync(GPUMapMode.READ);
            results[name] = Array.from(new Int32Array(read.getMappedRange())).slice(
              0, name === 'atomic-image' ? 4 : size / 4);
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
        assert results['readwrite-texture'] == [7, 0, 0, 0], results
        assert results['atomic-image'] == [1, 1024, 1, 0], results
        assert results['interface-names'] == [255, 128, 64, 255], results
        bins = [[] for _ in range(4096)]
        for index in range(256):
            for bin_index in range(index * 13, index * 13 + index % 31 + 1):
                bins[bin_index].append(index)
        expected = [(max(indices) << 16) | min(indices) if indices else 0xffff
                    for indices in bins]
        assert results['zbin-range'] == expected, 'packed light-bin extrema differ from CPU reference'
        (directory / 'semantics-validation.json').write_text(json.dumps({
            'results': results,
            'wgsl_sha256': {name: hashlib.sha256(code.encode()).hexdigest()
                            for name, code in sources.items()}}, indent=2) + '\n')
        browser.close()
    print('PASS: offline WebGPU switch control flow, 3D texel fetch, read/write storage and contended atomic images.')
finally:
    server.shutdown()
    server.server_close()
