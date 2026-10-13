/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

// Adapted for Blender 5.2.2 from HeyPuter/blender commit
// 6b031d3d41c392883e3c495aa72343e10d15b43d. See THIRD_PARTY.md.

/** \file
 * \ingroup GHOST
 * Browser window mapped to one canvas. This platform milestone uses a real
 * GHOST_ContextNone by default, with an opt-in real WebGPU canvas context.
 * Blender scene drawing and its editor renderer remain unimplemented.
 */

#pragma once

#include "GHOST_Window.hh"
#ifdef WITH_GHOST_WEBGPU_CONTEXT
#  include "GHOST_ContextWebGPU.hh"
#endif

#include <emscripten/emscripten.h>
#include <emscripten/html5.h>
#include <functional>
#ifdef WITH_WEBGPU_BACKEND
extern "C" void blender_webgpu_present(int width,int height);
#endif

class GHOST_WindowWeb : public GHOST_Window {
 private:
  uint32_t width_, height_;
  std::function<void()> request_redraw_;
  std::string title_;

 public:
  GHOST_WindowWeb(const char * /*title*/,
                  uint32_t width,
                  uint32_t height,
                  GHOST_TWindowState state,
                  const GHOST_ContextParams &context_params, std::function<void()> redraw)
      : GHOST_Window(width, height, state, context_params, false), width_(width), height_(height), request_redraw_(std::move(redraw)), title_("Blender")
  {
  }
  ~GHOST_WindowWeb() override = default;

  void resize(uint32_t width, uint32_t height)
  {
    width_ = width;
    height_ = height;
  }

  GHOST_TSuccess swapBufferAcquire() override
  {
    return drawing_context_type_ != GHOST_kDrawingContextTypeNone ?
      GHOST_Window::swapBufferAcquire() : GHOST_kFailure;
  }

  GHOST_TSuccess hasCursorShape(GHOST_TStandardCursor shape) override
  {
    return shape == GHOST_kStandardCursorDefault ? GHOST_kSuccess : GHOST_kFailure;
  }

 protected:
  GHOST_TSuccess setWindowCursorGrab(GHOST_TGrabCursorMode mode) override
  {
    return mode == GHOST_kGrabDisable ? GHOST_kSuccess : GHOST_kFailure;
  }
  GHOST_TSuccess setWindowCursorShape(GHOST_TStandardCursor shape) override
  {
    return shape == GHOST_kStandardCursorDefault ? GHOST_kSuccess : GHOST_kFailure;
  }
  GHOST_TSuccess setWindowCustomCursorShape(const uint8_t * /*bitmap*/,
                                            const uint8_t * /*mask*/,
                                            const int /*size*/[2],
                                            const int /*hot_spot*/[2],
                                            bool /*can_invert_color*/) override
  {
    return GHOST_kFailure;
  }
  GHOST_TSuccess setWindowCursorVisibility(bool visible) override
  {
    MAIN_THREAD_EM_ASM({ Module.canvas.style.cursor = $0 ? "default" : "none"; }, visible);
    return GHOST_kSuccess;
  }
 public:
  void setTitle(const char *title) override
  {
    title_ = title ? title : "";
    // Read the title synchronously on the browser thread, so a future worker
    // caller cannot release its string before the DOM update consumes it.
    MAIN_THREAD_EM_ASM({ document.title = UTF8ToString($0); }, title_.c_str());
  }
  std::string getTitle() const override
  {
    return title_;
  }
  void setPath(const char * /*filepath*/) override {}

  void getWindowBounds(GHOST_Rect &bounds) const override
  {
    getClientBounds(bounds);
  }
  void getClientBounds(GHOST_Rect &bounds) const override
  {
    bounds.l_ = 0;
    bounds.t_ = 0;
    bounds.r_ = int32_t(width_);
    bounds.b_ = int32_t(height_);
  }
  GHOST_TSuccess setClientWidth(uint32_t /*width*/) override
  {
    return GHOST_kFailure;
  }
  GHOST_TSuccess setClientHeight(uint32_t /*height*/) override
  {
    return GHOST_kFailure;
  }
  GHOST_TSuccess setClientSize(uint32_t /*width*/, uint32_t /*height*/) override
  {
    return GHOST_kFailure;
  }
  void screenToClient(int32_t inX, int32_t inY, int32_t &outX, int32_t &outY) const override
  {
    outX = inX;
    outY = inY;
  }
  void clientToScreen(int32_t inX, int32_t inY, int32_t &outX, int32_t &outY) const override
  {
    outX = inX;
    outY = inY;
  }
  GHOST_TSuccess swapBufferRelease() override
  {
#ifdef WITH_WEBGPU_BACKEND
    if (drawing_context_type_ == GHOST_kDrawingContextTypeWebGPU)
      blender_webgpu_present(width_,height_);
#endif
    return drawing_context_type_ != GHOST_kDrawingContextTypeNone ?
      GHOST_Window::swapBufferRelease() : GHOST_kFailure;
  }
  GHOST_Context *newDrawingContext(GHOST_TDrawingContextType type) override
  {
#ifdef WITH_GHOST_WEBGPU_CONTEXT
    if (type == GHOST_kDrawingContextTypeWebGPU) {
      auto *context = new GHOST_ContextWebGPU(want_context_params_);
      if (context->initializeDrawingContext() == GHOST_kSuccess) return context;
      delete context;
    }
#else
    (void)type;
#endif
    return nullptr;
  }
  float getNativePixelSize() override
  {
    return float(emscripten_get_device_pixel_ratio());
  }
  uint16_t getDPIHint() override
  {
    return uint16_t(96.0*emscripten_get_device_pixel_ratio());
  }
  GHOST_TSuccess setState(GHOST_TWindowState state) override
  {
    return state == GHOST_kWindowStateNormal ? GHOST_kSuccess : GHOST_kFailure;
  }
  GHOST_TWindowState getState() const override
  {
    return GHOST_kWindowStateNormal;
  }
  GHOST_TSuccess invalidate() override
  {
    request_redraw_();
    return GHOST_kSuccess;
  }
  GHOST_TSuccess setOrder(GHOST_TWindowOrder /*order*/) override
  {
    return GHOST_kFailure;
  }
};
