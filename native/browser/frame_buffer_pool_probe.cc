/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "webgpu/frame_buffer_pool.hh"
#include <emscripten.h>
#include <array>
#include <cassert>

static constexpr uint32_t frames = 60;
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
  EM_ASM({document.body.dataset.passed = 'true';});
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
  wgpuQueueRelease(queue);
  wgpuDeviceRelease(device);
  return 0;
}
