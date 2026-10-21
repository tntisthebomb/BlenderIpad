/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>
#include <webgpu/webgpu.h>

namespace blender::gpu {

/* Own fully overwritten buffers between frames. Retiring consumes one reference;
 * acquiring returns one owned reference, like CreateBuffer. A pending buffer
 * cannot be acquired until ALL commands referencing it have been submitted. */
class TransientBufferPool {
  struct Entry { WGPUBuffer buffer; uint64_t size; WGPUBufferUsage usage; };
  std::vector<Entry> pending_, reusable_;
  uint64_t bytes_ = 0;

 public:
  static constexpr uint64_t max_bytes = 8 * 1024 * 1024;
  static constexpr size_t max_buffers = 512;
  ~TransientBufferPool() { clear(); }
  TransientBufferPool() = default;
  TransientBufferPool(const TransientBufferPool &) = delete;
  TransientBufferPool &operator=(const TransientBufferPool &) = delete;

  WGPUBuffer acquire(WGPUDevice device, const WGPUBufferDescriptor &descriptor)
  {
    /* A later queue write executes after the preceding frame even if the GPU
     * has not finished it. No GPU completion wait is needed for reuse. */
    if (descriptor.nextInChain || descriptor.mappedAtCreation) {
      return wgpuDeviceCreateBuffer(device, &descriptor);
    }
    for (size_t i = 0; i < reusable_.size(); i++) {
      const Entry entry = reusable_[i];
      if (entry.size == descriptor.size && entry.usage == descriptor.usage) {
        reusable_[i] = reusable_.back();
        reusable_.pop_back();
        bytes_ -= entry.size;
        return entry.buffer;
      }
    }
    return wgpuDeviceCreateBuffer(device, &descriptor);
  }

  void retire(WGPUBuffer buffer, const WGPUBufferDescriptor &descriptor)
  {
    if (!buffer) return;
    if (descriptor.nextInChain || descriptor.mappedAtCreation || descriptor.size > 1024 * 1024) { wgpuBufferRelease(buffer); return; }
    /* Keep current working sizes ahead of unused buffers from an earlier scene. */
    while (!reusable_.empty() &&
           (bytes_ + descriptor.size > max_bytes || count() >= max_buffers)) {
      const Entry entry = reusable_.back();
      reusable_.pop_back();
      bytes_ -= entry.size;
      wgpuBufferRelease(entry.buffer);
    }
    if (bytes_ + descriptor.size > max_bytes || count() >= max_buffers) {
      wgpuBufferRelease(buffer);
      return;
    }
    pending_.push_back({buffer, descriptor.size, descriptor.usage});
    bytes_ += descriptor.size;
  }

  /* Call only after successful submission of every command using pending_. */
  void submitted()
  {
    reusable_.insert(reusable_.end(), pending_.begin(), pending_.end());
    pending_.clear();
  }
  uint64_t bytes() const { return bytes_; }
  size_t count() const { return pending_.size() + reusable_.size(); }
  void clear()
  {
    for (const Entry &entry : pending_) wgpuBufferRelease(entry.buffer);
    for (const Entry &entry : reusable_) wgpuBufferRelease(entry.buffer);
    pending_.clear(); reusable_.clear(); bytes_ = 0;
  }
};

}  // namespace blender::gpu
