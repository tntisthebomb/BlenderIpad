/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

// Adapted for Blender 5.2.2 from HeyPuter/blender commit
// 6b031d3d41c392883e3c495aa72343e10d15b43d. See THIRD_PARTY.md.

/** \file
 * \ingroup GHOST
 * Browser (Emscripten) GHOST system. Input arrives through emscripten/html5.h
 * callbacks registered on the browser thread. The caller must yield between
 * event-processing iterations. The current target is single-threaded; threaded
 * dispatch and the full WM main loop remain unimplemented. Exactly one window
 * exists, mapped to the page's #canvas.
 */

#pragma once

#include "GHOST_ContextNone.hh"
#include "GHOST_System.hh"
#include "GHOST_WindowWeb.hh"
#include <set>

class GHOST_SystemWeb : public GHOST_System {
 private:
#ifdef WITH_WEBGPU_BACKEND
  WGPUInstance graphics_instance_ = nullptr;
  WGPUDevice graphics_device_ = nullptr;
#endif
  GHOST_WindowWeb *window_ = nullptr;
  int32_t cursor_x_ = 0, cursor_y_ = 0;
  GHOST_Buttons buttons_;
  GHOST_ModifierKeys modifiers_;
  std::set<GHOST_TKey> pressed_keys_;
  int touch_id_ = -1;
  uint32_t canvas_w_ = 1280, canvas_h_ = 720;

 public:
  GHOST_SystemWeb();
  ~GHOST_SystemWeb() override;
  GHOST_TSuccess disposeWindow(GHOST_IWindow *window) override;

  bool processEvents(bool waitForEvent) override;

  bool setConsoleWindowState(GHOST_TConsoleWindowState /*action*/) override
  {
    return false;
  }
  GHOST_TSuccess getModifierKeys(GHOST_ModifierKeys &keys) const override
  {
    keys = modifiers_;
    return GHOST_kSuccess;
  }
  GHOST_TSuccess getButtons(GHOST_Buttons &buttons) const override
  {
    buttons = buttons_;
    return GHOST_kSuccess;
  }
  GHOST_TCapabilityFlag getCapabilities() const override
  {
    return GHOST_TCapabilityFlag(0); // Do not advertise unsupported desktop capabilities.
  }

  char *getClipboard(bool /*selection*/) const override
  {
    return nullptr;
  }
  void putClipboard(const char * /*buffer*/, bool /*selection*/) const override {}

  uint64_t getMilliSeconds() const override;

  uint8_t getNumDisplays() const override
  {
    return 1;
  }
  GHOST_TSuccess getCursorPosition(int32_t &x, int32_t &y) const override
  {
    x = cursor_x_;
    y = cursor_y_;
    return GHOST_kSuccess;
  }
  GHOST_TSuccess setCursorPosition(int32_t /*x*/, int32_t /*y*/) override
  {
    return GHOST_kFailure;
  }
  void getMainDisplayDimensions(uint32_t &width, uint32_t &height) const override
  {
    width = canvas_w_;
    height = canvas_h_;
  }
  void getAllDisplayDimensions(uint32_t &width, uint32_t &height) const override
  {
    getMainDisplayDimensions(width, height);
  }

  GHOST_IContext *createOffscreenContext(GHOST_GPUSettings gpu_settings) override
  {
    if (gpu_settings.context_type != GHOST_kDrawingContextTypeNone) return nullptr;
    const GHOST_ContextParams params = GHOST_CONTEXT_PARAMS_NONE;
    return new GHOST_ContextNone(params);
  }

  GHOST_TSuccess disposeContext(GHOST_IContext *context) override
  {
    delete context;
    return GHOST_kSuccess;
  }

  GHOST_IWindow *createWindow(const char *title,
                              int32_t /*left*/,
                              int32_t /*top*/,
                              uint32_t /*width*/,
                              uint32_t /*height*/,
                              GHOST_TWindowState state,
                              GHOST_GPUSettings gpu_settings,
                              const bool /*exclusive*/,
                              const bool /*is_dialog*/,
                              const GHOST_IWindow * /*parent_window*/) override;

  GHOST_IWindow *getWindowUnderCursor(int32_t x, int32_t y) override
  {
    return x >= 0 && y >= 0 && x < int32_t(canvas_w_) && y < int32_t(canvas_h_) ? window_ : nullptr;
  }

  GHOST_WindowWeb *window_get()
  {
    return window_;
  }

  /* html5 callback handlers (public: called from static trampolines). */
  bool handleMouse(int event_type, const struct EmscriptenMouseEvent *e);
  bool handleWheel(const struct EmscriptenWheelEvent *e);
  bool handleKey(int event_type, const struct EmscriptenKeyboardEvent *e);
  bool handleResize();
  bool handleTouch(int type, const struct EmscriptenTouchEvent *event);
  bool handleBlur();
  bool handleFocus();

 protected:
  GHOST_TSuccess init() override;
};
