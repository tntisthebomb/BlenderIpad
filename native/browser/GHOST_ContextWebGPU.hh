/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "GHOST_Context.hh"
#include <webgpu/webgpu.h>

/** Main-thread canvas context. GPU bootstrap handles are borrowed until init;
 * each initialized context then owns references independently. */
class GHOST_ContextWebGPU : public GHOST_Context {
  static inline thread_local WGPUInstance bootstrap_instance_ = nullptr;
  static inline thread_local WGPUDevice bootstrap_device_ = nullptr;
  WGPUDevice device_ = nullptr;
  WGPUSurface surface_ = nullptr;
  WGPUTexture texture_ = nullptr;
  WGPUTextureView view_ = nullptr;
  WGPUTextureFormat format_ = WGPUTextureFormat_Undefined;
  int width_ = 0, height_ = 0;
  bool submitted_ = false;
  void discardFrame();
 public:
  explicit GHOST_ContextWebGPU(const GHOST_ContextParams &params) : GHOST_Context(params) {}
  ~GHOST_ContextWebGPU() override;
  static void setBootstrap(WGPUInstance instance, WGPUDevice device)
  {
    bootstrap_instance_ = instance; bootstrap_device_ = device;
  }
  WGPUDevice device() const { return device_; }
  WGPUTexture texture() const { return texture_; }
  WGPUTextureView view() const { return view_; }
  WGPUTextureFormat format() const { return format_; }
  GHOST_TSuccess submit(WGPUCommandBuffer command);
  GHOST_TSuccess initializeDrawingContext() override;
  GHOST_TSuccess updateDrawingContext() override;
  GHOST_TSuccess activateDrawingContext() override;
  GHOST_TSuccess releaseDrawingContext() override;
  GHOST_TSuccess swapBufferAcquire() override;
  GHOST_TSuccess swapBufferRelease() override;
  GHOST_TSuccess releaseNativeHandles() override;
};
