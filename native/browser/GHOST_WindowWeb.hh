/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

// Adapted for Blender 5.2.2 from HeyPuter/blender commit
// 6b031d3d41c392883e3c495aa72343e10d15b43d. See THIRD_PARTY.md.

/** \file
 * \ingroup GHOST
 * Browser window mapped to one canvas. This platform milestone uses a real
 * GHOST_ContextNone for event/window integration. No graphics backend is
 * attached: presentation explicitly fails until a renderer is implemented.
 */

#pragma once

#include "GHOST_Window.hh"

#include <emscripten/emscripten.h>
#include <functional>

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
    return GHOST_kFailure; // No graphics backend is attached yet.
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
    return GHOST_kFailure; // Presentation is not implemented; do not report success.
  }
  GHOST_Context *newDrawingContext(GHOST_TDrawingContextType /*type*/) override
  {
    return nullptr;
  }
  GHOST_TSuccess activateDrawingContext() override
  {
    return GHOST_Window::activateDrawingContext();
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
