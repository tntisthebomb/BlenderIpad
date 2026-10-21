/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include <cstring>
#include <vector>
#include "frame_buffer_pool.hh"

namespace blender::gpu {

/* Small texture updates remain ordered with preceding draws without a submit.
 * Large uploads retain the existing guarded QueueWriteTexture path. */
class TextureUploadStaging {
  std::vector<uint8_t> padded_;
 public:
  static constexpr uint64_t max_bytes = 1024 * 1024;
  static uint64_t padded_size(size_t source_size,
                              const WGPUTexelCopyBufferLayout &layout,
                              const WGPUExtent3D &extent)
  {
    const uint64_t row = layout.bytesPerRow;
    if (layout.offset || !row || row > max_bytes || !extent.height ||
        !extent.depthOrArrayLayers || layout.rowsPerImage != extent.height) return 0;
    const uint64_t stride = (row + 255) & ~uint64_t(255);
    if (extent.height > max_bytes / stride) return 0;
    const uint64_t image = stride * extent.height;
    if (extent.depthOrArrayLayers > max_bytes / image) return 0;
    if (source_size < row * extent.height * extent.depthOrArrayLayers) return 0;
    return image * extent.depthOrArrayLayers;
  }

  bool record(WGPUDevice device, WGPUQueue queue, WGPUCommandEncoder encoder,
              TransientBufferPool &pool, const WGPUTexelCopyTextureInfo &destination,
              const void *source, size_t source_size,
              const WGPUTexelCopyBufferLayout &layout, const WGPUExtent3D &extent)
  {
    const uint64_t size = padded_size(source_size, layout, extent);
    if (!size || !source || !encoder) return false;
    const uint64_t row = layout.bytesPerRow;
    const uint64_t stride = (row + 255) & ~uint64_t(255);
    const void *upload = source;
    if (stride != row) {
      padded_.resize(size);
      const auto *bytes = static_cast<const uint8_t *>(source);
      for (uint64_t i = 0; i < uint64_t(extent.height) * extent.depthOrArrayLayers; i++) {
        std::memcpy(padded_.data() + i * stride, bytes + i * row, row);
      }
      upload = padded_.data();
    }
    WGPUBufferDescriptor descriptor = WGPU_BUFFER_DESCRIPTOR_INIT;
    descriptor.label = {"texture upload staging", WGPU_STRLEN};
    descriptor.size = size;
    descriptor.usage = WGPUBufferUsage_CopySrc | WGPUBufferUsage_CopyDst;
    auto buffer = pool.acquire(device, descriptor);
    if (!buffer) return false;
    wgpuQueueWriteBuffer(queue, buffer, 0, upload, size);
    WGPUTexelCopyBufferInfo copy = {};
    copy.buffer = buffer;
    copy.layout.bytesPerRow = uint32_t(stride);
    copy.layout.rowsPerImage = extent.height;
    wgpuCommandEncoderCopyBufferToTexture(encoder, &copy, &destination, &extent);
    pool.retire(buffer, descriptor);
    return true;
  }
};

}  // namespace blender::gpu
