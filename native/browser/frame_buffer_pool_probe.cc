/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "webgpu/frame_buffer_pool.hh"
#include "webgpu/texture_upload.hh"
#include <emscripten.h>
#include <array>
#include <cassert>

static constexpr uint32_t frames = 60;
static int completed_cases = 0;
static void complete_case()
{
  if (++completed_cases == 3) EM_ASM({document.body.dataset.passed = 'true';});
}
struct TextureRead {
  WGPUBuffer buffer;
  uint32_t layers;
};
static uint8_t expected_texel(int phase, int layer, int row, int x, int channel)
{
  return uint8_t(phase * 71 + layer * 31 + row * 17 + x * 3 + channel);
}
static void texture_mapped(WGPUMapAsyncStatus status, WGPUStringView, void *user, void *)
{
  auto *read = static_cast<TextureRead *>(user);
  assert(status == WGPUMapAsyncStatus_Success);
  const uint64_t image_bytes = 256 * 2, phase_bytes = image_bytes * read->layers;
  const auto *pixels = static_cast<const uint8_t *>(
      wgpuBufferGetConstMappedRange(read->buffer, 0, phase_bytes * 2));
  assert(pixels);
  for (int phase = 0; phase < 2; phase++) for (uint32_t layer = 0; layer < read->layers; layer++) {
    for (int row = 0; row < 2; row++) for (int x = 0; x < 7; x++) for (int channel = 0; channel < 4; channel++) {
      assert(pixels[phase * phase_bytes + layer * image_bytes + row * 256 + x * 4 + channel] ==
             expected_texel(phase, layer, row, x, channel));
    }
  }
  wgpuBufferUnmap(read->buffer);
  wgpuBufferRelease(read->buffer);
  delete read;
  complete_case();
}
static void texture_case(WGPUDevice device, WGPUQueue queue, bool volume)
{
  blender::gpu::TransientBufferPool pool;
  blender::gpu::TextureUploadStaging staging;
  WGPUTextureDescriptor descriptor = WGPU_TEXTURE_DESCRIPTOR_INIT;
  descriptor.dimension = volume ? WGPUTextureDimension_3D : WGPUTextureDimension_2D;
  descriptor.size = volume ? WGPUExtent3D{9, 4, 3} : WGPUExtent3D{20, 8, 2};
  descriptor.mipLevelCount = volume ? 1 : 2;
  descriptor.format = WGPUTextureFormat_RGBA8Unorm;
  descriptor.usage = WGPUTextureUsage_CopySrc | WGPUTextureUsage_CopyDst;
  auto texture = wgpuDeviceCreateTexture(device, &descriptor);
  const WGPUExtent3D extent = {7, 2, volume ? 2u : 1u};
  const uint64_t phase_bytes = 256 * extent.height * extent.depthOrArrayLayers;
  WGPUBufferDescriptor output_descriptor = WGPU_BUFFER_DESCRIPTOR_INIT;
  output_descriptor.size = phase_bytes * 2;
  output_descriptor.usage = WGPUBufferUsage_CopyDst | WGPUBufferUsage_MapRead;
  auto output = wgpuDeviceCreateBuffer(device, &output_descriptor);
  auto encoder = wgpuDeviceCreateCommandEncoder(device, nullptr);
  WGPUTexelCopyTextureInfo destination = {};
  destination.texture = texture;
  destination.mipLevel = volume ? 0 : 1;
  destination.origin = {1, 1, 1};
  destination.aspect = WGPUTextureAspect_All;
  WGPUTexelCopyBufferLayout layout = {};
  layout.bytesPerRow = 7 * 4;
  layout.rowsPerImage = 2;
  std::vector<uint8_t> source(7 * 4 * extent.height * extent.depthOrArrayLayers);
  for (int phase = 0; phase < 2; phase++) {
    for (uint32_t layer = 0; layer < extent.depthOrArrayLayers; layer++) {
      for (int row = 0; row < 2; row++) for (int x = 0; x < 7; x++) for (int channel = 0; channel < 4; channel++) {
        source[(layer * 2 + row) * 7 * 4 + x * 4 + channel] = expected_texel(phase, layer, row, x, channel);
      }
    }
    assert(staging.record(device, queue, encoder, pool, destination, source.data(), source.size(), layout, extent));
    WGPUTexelCopyBufferInfo target = {};
    target.buffer = output;
    target.layout.offset = phase * phase_bytes;
    target.layout.bytesPerRow = 256;
    target.layout.rowsPerImage = 2;
    wgpuCommandEncoderCopyTextureToBuffer(encoder, &destination, &target, &extent);
  }
  /* Both updates and both observations share ONE submission. The second
   * upload must never retroactively replace what the first observation sees. */
  auto command = wgpuCommandEncoderFinish(encoder, nullptr);
  wgpuQueueSubmit(queue, 1, &command);
  wgpuCommandBufferRelease(command);
  wgpuCommandEncoderRelease(encoder);
  pool.submitted();
  pool.clear();
  wgpuTextureRelease(texture);
  WGPUBufferMapCallbackInfo callback = WGPU_BUFFER_MAP_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_AllowSpontaneous;
  callback.callback = texture_mapped;
  callback.userdata1 = new TextureRead{output, extent.depthOrArrayLayers};
  wgpuBufferMapAsync(output, WGPUMapMode_Read, 0, phase_bytes * 2, callback);
}

static void mapped(WGPUMapAsyncStatus status, WGPUStringView, void *user, void *)
{
  auto buffer = static_cast<WGPUBuffer>(user);
  assert(status == WGPUMapAsyncStatus_Success);
  const auto *values = static_cast<const uint32_t *>(
      wgpuBufferGetConstMappedRange(buffer, 0, frames * 16));
  assert(values);
  for (uint32_t frame = 0; frame < frames; frame++) {
    for (uint32_t word = 0; word < 4; word++) assert(values[frame * 4 + word] == frame + 1);
  }
  wgpuBufferUnmap(buffer);
  wgpuBufferRelease(buffer);
  complete_case();
}

int main()
{
  auto device = emscripten_webgpu_get_device();
  auto queue = wgpuDeviceGetQueue(device);
  blender::gpu::TransientBufferPool pool;
  WGPUBufferDescriptor descriptor = WGPU_BUFFER_DESCRIPTOR_INIT;
  descriptor.size = 16;
  descriptor.usage = WGPUBufferUsage_Storage | WGPUBufferUsage_CopySrc | WGPUBufferUsage_CopyDst;
  WGPUBufferDescriptor output_descriptor = WGPU_BUFFER_DESCRIPTOR_INIT;
  output_descriptor.size = frames * 16;
  output_descriptor.usage = WGPUBufferUsage_CopyDst | WGPUBufferUsage_MapRead;
  auto output = wgpuDeviceCreateBuffer(device, &output_descriptor);
  WGPUBuffer previous = nullptr;
  for (uint32_t frame = 0; frame < frames; frame++) {
    auto buffer = pool.acquire(device, descriptor);
    assert(buffer && (!previous || buffer == previous));
    const std::array<uint32_t, 4> value = {frame + 1, frame + 1, frame + 1, frame + 1};
    wgpuQueueWriteBuffer(queue, buffer, 0, value.data(), sizeof(value));
    auto encoder = wgpuDeviceCreateCommandEncoder(device, nullptr);
    wgpuCommandEncoderCopyBufferToBuffer(encoder, buffer, 0, output, frame * 16, 16);
    pool.retire(buffer, descriptor);
    if (!frame) {
      auto premature = pool.acquire(device, descriptor);
      assert(premature != buffer); /* The first frame is still unsubmitted. */
      wgpuBufferRelease(premature);
    }
    auto command = wgpuCommandEncoderFinish(encoder, nullptr);
    wgpuQueueSubmit(queue, 1, &command);
    wgpuCommandBufferRelease(command);
    wgpuCommandEncoderRelease(encoder);
    pool.submitted();
    previous = buffer;
  }
  /* Release pool ownership before readback; the queued commands must keep
   * every old frame's input alive and observe its value, rather than the last. */
  pool.clear();
  assert(pool.count() == 0 && pool.bytes() == 0);
  descriptor.size = 1024 * 1024;
  for (int i = 0; i < 16; i++) pool.retire(pool.acquire(device, descriptor), descriptor);
  assert(pool.bytes() <= pool.max_bytes && pool.count() <= pool.max_buffers);
  pool.clear();
  descriptor.size = 4;
  for (int i = 0; i < 600; i++) pool.retire(pool.acquire(device, descriptor), descriptor);
  assert(pool.count() == pool.max_buffers);
  const auto count = pool.count();
  descriptor.size = 2 * 1024 * 1024;
  pool.retire(pool.acquire(device, descriptor), descriptor);
  assert(pool.count() == count); /* Large buffers must bypass the pool. */
  pool.clear();
  WGPUBufferMapCallbackInfo callback = WGPU_BUFFER_MAP_CALLBACK_INFO_INIT;
  callback.mode = WGPUCallbackMode_AllowSpontaneous;
  callback.callback = mapped;
  callback.userdata1 = output;
  wgpuBufferMapAsync(output, WGPUMapMode_Read, 0, frames * 16, callback);
  texture_case(device, queue, false);
  texture_case(device, queue, true);
  wgpuQueueRelease(queue);
  wgpuDeviceRelease(device);
  return 0;
}
