/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "GHOST_ContextWebGPU.hh"
#include <emscripten.h>
#include <emscripten/html5.h>
#include <emscripten/threading.h>

void GHOST_ContextWebGPU::discardFrame()
{
  if (view_) wgpuTextureViewRelease(view_);
  if (texture_) wgpuTextureRelease(texture_);
  view_ = nullptr; texture_ = nullptr; submitted_ = false;
}
GHOST_ContextWebGPU::~GHOST_ContextWebGPU()
{
  releaseNativeHandles();
}
GHOST_TSuccess GHOST_ContextWebGPU::initializeDrawingContext()
{
  if (!emscripten_is_main_browser_thread() || !bootstrap_instance_ || !bootstrap_device_ || surface_)
    return GHOST_kFailure;
  WGPUEmscriptenSurfaceSourceCanvasHTMLSelector canvas = WGPU_EMSCRIPTEN_SURFACE_SOURCE_CANVAS_HTML_SELECTOR_INIT;
  canvas.selector = {"#canvas", WGPU_STRLEN};
  WGPUSurfaceDescriptor descriptor = WGPU_SURFACE_DESCRIPTOR_INIT;
  descriptor.nextInChain = &canvas.chain;
  surface_ = wgpuInstanceCreateSurface(bootstrap_instance_, &descriptor);
  if (!surface_) return GHOST_kFailure;
  device_ = bootstrap_device_;
  wgpuDeviceAddRef(device_);
  format_ = WGPUTextureFormat(EM_ASM_INT({
    return navigator.gpu.getPreferredCanvasFormat() === 'bgra8unorm' ? $0 : $1;
  }, int(WGPUTextureFormat_BGRA8Unorm), int(WGPUTextureFormat_RGBA8Unorm)));
  if (updateDrawingContext() != GHOST_kSuccess) {
    releaseNativeHandles(); return GHOST_kFailure;
  }
  return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::updateDrawingContext()
{
  int width, height;
  if (!surface_ || !emscripten_is_main_browser_thread() || texture_ ||
      emscripten_get_canvas_element_size("#canvas", &width, &height) != EMSCRIPTEN_RESULT_SUCCESS ||
      width <= 0 || height <= 0) return GHOST_kFailure;
  if (width == width_ && height == height_) return GHOST_kSuccess;
  WGPUSurfaceConfiguration config = WGPU_SURFACE_CONFIGURATION_INIT;
  config.device = device_; config.format = format_;
  config.width = uint32_t(width); config.height = uint32_t(height);
  config.usage = WGPUTextureUsage_RenderAttachment | WGPUTextureUsage_CopySrc;
  config.alphaMode = WGPUCompositeAlphaMode_Opaque;
  config.presentMode = WGPUPresentMode_Fifo;
  wgpuSurfaceConfigure(surface_, &config);
  width_ = width; height_ = height;
  return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::activateDrawingContext()
{
  if (!device_ || !emscripten_is_main_browser_thread()) return GHOST_kFailure;
  active_context_ = this; return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::releaseDrawingContext()
{
  if (active_context_ != this) return GHOST_kFailure;
  active_context_ = nullptr; return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::swapBufferAcquire()
{
  if (active_context_ != this || texture_ || updateDrawingContext() != GHOST_kSuccess)
    return GHOST_kFailure;
  WGPUSurfaceTexture frame = WGPU_SURFACE_TEXTURE_INIT;
  wgpuSurfaceGetCurrentTexture(surface_, &frame);
  if (frame.status != WGPUSurfaceGetCurrentTextureStatus_SuccessOptimal &&
      frame.status != WGPUSurfaceGetCurrentTextureStatus_SuccessSuboptimal) {
    if (frame.texture) wgpuTextureRelease(frame.texture);
    return GHOST_kFailure;
  }
  texture_ = frame.texture;
  if (!texture_) return GHOST_kFailure;
  view_ = wgpuTextureCreateView(texture_, nullptr);
  if (!view_) { discardFrame(); return GHOST_kFailure; }
  return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::submit(WGPUCommandBuffer command)
{
  if (active_context_ != this || !view_ || !command) return GHOST_kFailure;
  WGPUQueue queue = wgpuDeviceGetQueue(device_);
  if (!queue) return GHOST_kFailure;
  wgpuQueueSubmit(queue, 1, &command); wgpuQueueRelease(queue);
  submitted_ = true; return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::swapBufferRelease()
{
  if (active_context_ != this || !texture_ || !submitted_) return GHOST_kFailure;
  // Browser presentation happens when the animation frame yields. The native
  // wgpuSurfacePresent call aborts on the web and must never be invoked here.
  discardFrame(); return GHOST_kSuccess;
}
GHOST_TSuccess GHOST_ContextWebGPU::releaseNativeHandles()
{
  discardFrame();
  if (surface_) { wgpuSurfaceUnconfigure(surface_); wgpuSurfaceRelease(surface_); }
  if (device_) wgpuDeviceRelease(device_);
  if (active_context_ == this) active_context_ = nullptr;
  surface_ = nullptr; device_ = nullptr; width_ = height_ = 0;
  return GHOST_kSuccess;
}
