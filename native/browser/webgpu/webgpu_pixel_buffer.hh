/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "gpu_texture_private.hh"
#include <vector>
#include <stdexcept>
namespace blender::gpu {
class WebGPUPixelBuffer : public PixelBuffer {
  std::vector<uint8_t> bytes_;
  bool mapped_=false;
 public:
  explicit WebGPUPixelBuffer(size_t size) : PixelBuffer(size),bytes_(size) {}
  void *map() override
  {
    if (mapped_) throw std::runtime_error("WebGPU pixel buffer already mapped");
    mapped_=true;return bytes_.data();
  }
  void unmap() override
  {
    if (!mapped_) throw std::runtime_error("WebGPU pixel buffer is not mapped");
    mapped_=false;
  }
  const void *data() const { return bytes_.data(); }
  GPUPixelBufferNativeHandle get_native_handle() override
  {
    throw std::runtime_error("Browser pixel buffers do not expose OS GPU handles");
  }
  size_t get_size() override { return size_; }
};

}
