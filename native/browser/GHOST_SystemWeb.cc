/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

// Adapted for Blender 5.2.2 from HeyPuter/blender commit
// 6b031d3d41c392883e3c495aa72343e10d15b43d. See THIRD_PARTY.md.

/** \file
 * \ingroup GHOST
 */

#include <cstring>
#include <cstdlib>

#include <emscripten/emscripten.h>
#include <emscripten/html5.h>

#include "GHOST_EventButton.hh"
#include "GHOST_EventCursor.hh"
#include "GHOST_EventKey.hh"
#include "GHOST_EventWheel.hh"
#include "GHOST_SystemWeb.hh"
#include "GHOST_TimerManager.hh"
#include "GHOST_WindowManager.hh"

#define WEB_CANVAS "#canvas"

/* --- Static trampolines ----------------------------------------------------- */

static EM_BOOL web_mouse_cb(int type, const EmscriptenMouseEvent *e, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleMouse(type, e);
}
static EM_BOOL web_wheel_cb(int /*type*/, const EmscriptenWheelEvent *e, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleWheel(e);
}
static EM_BOOL web_key_cb(int type, const EmscriptenKeyboardEvent *e, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleKey(type, e);
}
static EM_BOOL web_resize_cb(int /*type*/, const EmscriptenUiEvent * /*e*/, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleResize();
}

static EM_BOOL web_touch_cb(int type, const EmscriptenTouchEvent *event, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleTouch(type, event);
}
static EM_BOOL web_focus_cb(int, const EmscriptenFocusEvent *, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleFocus();
}
static EM_BOOL web_blur_cb(int, const EmscriptenFocusEvent *, void *user)
{
  return static_cast<GHOST_SystemWeb *>(user)->handleBlur();
}

/* --- Key mapping ------------------------------------------------------------ */

static GHOST_TKey web_key_from_code(const char *code)
{
  /* `code` is the PHYSICAL key (KeyboardEvent.code). */
  if (strncmp(code, "Key", 3) == 0 && code[3] >= 'A' && code[3] <= 'Z' && code[4] == '\0') {
    return GHOST_TKey(int(GHOST_kKeyA) + (code[3] - 'A'));
  }
  if (strncmp(code, "Digit", 5) == 0 && code[5] >= '0' && code[5] <= '9' && code[6] == '\0') {
    return GHOST_TKey(int(GHOST_kKey0) + (code[5] - '0'));
  }
  if (strncmp(code, "Numpad", 6) == 0 && code[6] >= '0' && code[6] <= '9' && code[7] == '\0') {
    return GHOST_TKey(int(GHOST_kKeyNumpad0) + (code[6] - '0'));
  }
  if (code[0] == 'F' && code[1] >= '1' && code[1] <= '9') {
    int num = atoi(code + 1);
    if (num >= 1 && num <= 24) {
      return GHOST_TKey(int(GHOST_kKeyF1) + num - 1);
    }
  }
  struct {
    const char *code;
    GHOST_TKey key;
  } table[] = {
      {"Space", GHOST_kKeySpace},
      {"Enter", GHOST_kKeyEnter},
      {"NumpadEnter", GHOST_kKeyNumpadEnter},
      {"Escape", GHOST_kKeyEsc},
      {"Tab", GHOST_kKeyTab},
      {"Backspace", GHOST_kKeyBackSpace},
      {"Delete", GHOST_kKeyDelete},
      {"Insert", GHOST_kKeyInsert},
      {"Home", GHOST_kKeyHome},
      {"End", GHOST_kKeyEnd},
      {"PageUp", GHOST_kKeyUpPage},
      {"PageDown", GHOST_kKeyDownPage},
      {"ArrowLeft", GHOST_kKeyLeftArrow},
      {"ArrowRight", GHOST_kKeyRightArrow},
      {"ArrowUp", GHOST_kKeyUpArrow},
      {"ArrowDown", GHOST_kKeyDownArrow},
      {"ShiftLeft", GHOST_kKeyLeftShift},
      {"ShiftRight", GHOST_kKeyRightShift},
      {"ControlLeft", GHOST_kKeyLeftControl},
      {"ControlRight", GHOST_kKeyRightControl},
      {"AltLeft", GHOST_kKeyLeftAlt},
      {"AltRight", GHOST_kKeyRightAlt},
      {"MetaLeft", GHOST_kKeyLeftOS},
      {"MetaRight", GHOST_kKeyRightOS},
      {"Minus", GHOST_kKeyMinus},
      {"Equal", GHOST_kKeyEqual},
      {"BracketLeft", GHOST_kKeyLeftBracket},
      {"BracketRight", GHOST_kKeyRightBracket},
      {"Backslash", GHOST_kKeyBackslash},
      {"Semicolon", GHOST_kKeySemicolon},
      {"Quote", GHOST_kKeyQuote},
      {"Backquote", GHOST_kKeyAccentGrave},
      {"Comma", GHOST_kKeyComma},
      {"Period", GHOST_kKeyPeriod},
      {"Slash", GHOST_kKeySlash},
      {"CapsLock", GHOST_kKeyCapsLock},
      {"NumpadAdd", GHOST_kKeyNumpadPlus},
      {"NumpadSubtract", GHOST_kKeyNumpadMinus},
      {"NumpadMultiply", GHOST_kKeyNumpadAsterisk},
      {"NumpadDivide", GHOST_kKeyNumpadSlash},
      {"NumpadDecimal", GHOST_kKeyNumpadPeriod},
  };
  for (const auto &entry : table) {
    if (strcmp(code, entry.code) == 0) {
      return entry.key;
    }
  }
  return GHOST_kKeyUnknown;
}

/* --- System ------------------------------------------------------------------ */

GHOST_SystemWeb::GHOST_SystemWeb() : GHOST_System() {}
GHOST_SystemWeb::~GHOST_SystemWeb()
{
  emscripten_set_mousedown_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_mouseup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, nullptr, false, nullptr);
  emscripten_set_mousemove_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_wheel_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_keydown_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_keyup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, nullptr, false, nullptr);
  emscripten_set_resize_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, nullptr, false, nullptr);
  emscripten_set_blur_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_focus_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_touchstart_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_touchmove_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_touchend_callback(WEB_CANVAS, nullptr, false, nullptr);
  emscripten_set_touchcancel_callback(WEB_CANVAS, nullptr, false, nullptr);
  if (window_) disposeWindow(window_);
}
GHOST_TSuccess GHOST_SystemWeb::disposeWindow(GHOST_IWindow *window)
{
  const bool is_browser_window = window == window_;
  const auto success = GHOST_System::disposeWindow(window);
  if (is_browser_window && success == GHOST_kSuccess) {
    window_ = nullptr;
    pressed_keys_.clear(); buttons_.clear(); modifiers_.clear(); touch_id_ = -1;
  }
  return success;
}

GHOST_TSuccess GHOST_SystemWeb::init()
{
  GHOST_TSuccess success = GHOST_System::init();
  if (!success) {
    return GHOST_kFailure;
  }

  /* Canvas size: authoritative from the page (set once by the harness). */
  double w = 0, h = 0;
  if (emscripten_get_element_css_size(WEB_CANVAS, &w, &h) == EMSCRIPTEN_RESULT_SUCCESS && w > 0) {
    canvas_w_ = uint32_t(w);
    canvas_h_ = uint32_t(h);
  }

  /* Input callbacks, delivered on this (the Blender main) thread whenever it
   * yields to its event loop. */
  emscripten_set_mousedown_callback(WEB_CANVAS, this, false, web_mouse_cb);
  emscripten_set_mouseup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, this, false, web_mouse_cb);
  emscripten_set_mousemove_callback(WEB_CANVAS, this, false, web_mouse_cb);
  emscripten_set_wheel_callback(WEB_CANVAS, this, false, web_wheel_cb);
  emscripten_set_keydown_callback(WEB_CANVAS, this, false, web_key_cb);
  emscripten_set_keyup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, this, false, web_key_cb);
  emscripten_set_resize_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, this, false, web_resize_cb);
  emscripten_set_blur_callback(WEB_CANVAS, this, false, web_blur_cb);
  emscripten_set_focus_callback(WEB_CANVAS, this, false, web_focus_cb);
  emscripten_set_touchstart_callback(WEB_CANVAS, this, false, web_touch_cb);
  emscripten_set_touchmove_callback(WEB_CANVAS, this, false, web_touch_cb);
  emscripten_set_touchend_callback(WEB_CANVAS, this, false, web_touch_cb);
  emscripten_set_touchcancel_callback(WEB_CANVAS, this, false, web_touch_cb);
  MAIN_THREAD_EM_ASM({ Module.canvas.tabIndex = 0; Module.canvas.style.touchAction = "none";
    Module.canvas.style.userSelect = "none"; Module.canvas.style.webkitUserSelect = "none";
    Module.canvas.style.webkitTouchCallout = "none"; });
  return GHOST_kSuccess;
}

uint64_t GHOST_SystemWeb::getMilliSeconds() const
{
  return uint64_t(emscripten_get_now());
}

bool GHOST_SystemWeb::processEvents(bool /*waitForEvent*/)
{
  /* html5 callbacks have already pushed into the event queue (they run when the
   * main-loop iteration yields). Fire timers too. */
  bool has_event = false;
  if (timer_manager_) {
    has_event |= timer_manager_->fireTimers(getMilliSeconds());
  }
  has_event |= (event_manager_->getNumEvents() > 0);
  return has_event;
}

GHOST_IWindow *GHOST_SystemWeb::createWindow(const char *title,
                                             int32_t /*left*/,
                                             int32_t /*top*/,
                                             uint32_t /*width*/,
                                             uint32_t /*height*/,
                                             GHOST_TWindowState state,
                                             GHOST_GPUSettings gpu_settings,
                                             const bool /*exclusive*/,
                                             const bool /*is_dialog*/,
                                             const GHOST_IWindow * /*parent_window*/)
{
  if (gpu_settings.context_type != GHOST_kDrawingContextTypeNone
#ifdef WITH_GHOST_WEBGPU_CONTEXT
      && gpu_settings.context_type != GHOST_kDrawingContextTypeWebGPU
#endif
  ) return nullptr;
  if (window_ != nullptr) {
    /* Single-window platform: additional windows (preferences, etc.) are not
     * supported; return null so WM falls back to opening in the main window. */
    return nullptr;
  }
  const GHOST_ContextParams context_params = GHOST_CONTEXT_PARAMS_FROM_GPU_SETTINGS(gpu_settings);
  window_ = new GHOST_WindowWeb(title, canvas_w_, canvas_h_, state, context_params, [this]() {
    pushEvent(std::make_unique<GHOST_Event>(getMilliSeconds(), GHOST_kEventWindowUpdate, window_));
  });
  if (window_->setDrawingContextType(gpu_settings.context_type) != GHOST_kSuccess) {
    delete window_; window_ = nullptr; return nullptr;
  }
  window_->setTitle(title);
  /* Register with the window manager so validWindow() passes — otherwise every
   * GHOST event is dropped as "invalid window" in wm_window's event handler. */
  window_manager_->addWindow(window_);
  window_manager_->setActiveWindow(window_);
  pushEvent(std::unique_ptr<const GHOST_IEvent>(
      new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowSize, window_)));
  return window_;
}

/* --- Event handlers ----------------------------------------------------------- */

bool GHOST_SystemWeb::handleMouse(int event_type, const EmscriptenMouseEvent *e)
{
  if (window_ == nullptr) {
    return false;
  }
  const uint64_t t = getMilliSeconds();
  cursor_x_ = EM_ASM_INT({ return $0 - Module.canvas.getBoundingClientRect().left; }, e->clientX);
  cursor_y_ = EM_ASM_INT({ return $0 - Module.canvas.getBoundingClientRect().top; }, e->clientY);
  if (event_type == EMSCRIPTEN_EVENT_MOUSEDOWN) {
    MAIN_THREAD_EM_ASM({ Module.canvas.focus({preventScroll:true}); });
  }

  const auto sync_modifier = [this](GHOST_TModifierKey left, GHOST_TModifierKey right, bool held) {
    if (!held) { modifiers_.set(left, false); modifiers_.set(right, false); }
    else if (!modifiers_.get(left) && !modifiers_.get(right)) modifiers_.set(left, true);
  };
  sync_modifier(GHOST_kModifierKeyLeftShift, GHOST_kModifierKeyRightShift, e->shiftKey);
  sync_modifier(GHOST_kModifierKeyLeftControl, GHOST_kModifierKeyRightControl, e->ctrlKey);
  sync_modifier(GHOST_kModifierKeyLeftAlt, GHOST_kModifierKeyRightAlt, e->altKey);
  sync_modifier(GHOST_kModifierKeyLeftOS, GHOST_kModifierKeyRightOS, e->metaKey);

  switch (event_type) {
    case EMSCRIPTEN_EVENT_MOUSEMOVE:
      pushEvent(std::unique_ptr<const GHOST_IEvent>(new GHOST_EventCursor(
          t, GHOST_kEventCursorMove, window_, cursor_x_, cursor_y_, GHOST_TABLET_DATA_NONE)));
      return true;
    case EMSCRIPTEN_EVENT_MOUSEDOWN:
    case EMSCRIPTEN_EVENT_MOUSEUP: {
      GHOST_TButton button = (e->button == 0) ? GHOST_kButtonMaskLeft :
                             (e->button == 1) ? GHOST_kButtonMaskMiddle :
                                                GHOST_kButtonMaskRight;
      const bool down = (event_type == EMSCRIPTEN_EVENT_MOUSEDOWN);
      if (!down && !buttons_.get(button)) return false;
      buttons_.set(button, down);
      pushEvent(std::unique_ptr<const GHOST_IEvent>(new GHOST_EventButton(t,
                                      down ? GHOST_kEventButtonDown : GHOST_kEventButtonUp,
                                      window_,
                                      button,
                                      GHOST_TABLET_DATA_NONE)));
      return true;
    }
    default:
      return false;
  }
}

bool GHOST_SystemWeb::handleWheel(const EmscriptenWheelEvent *e)
{
  if (!window_ || (e->deltaY == 0.0 && e->deltaX == 0.0)) return false;
  const bool vertical = e->deltaY != 0.0;
  const double delta = vertical ? e->deltaY : e->deltaX;
  pushEvent(std::make_unique<GHOST_EventWheel>(getMilliSeconds(), window_,
    vertical ? GHOST_kEventWheelAxisVertical : GHOST_kEventWheelAxisHorizontal, delta > 0 ? -1 : 1));
  return true;
}

bool GHOST_SystemWeb::handleKey(int event_type, const EmscriptenKeyboardEvent *e)
{
  if (window_ == nullptr) {
    return false;
  }
  const GHOST_TKey key = web_key_from_code(e->code);
  if (key == GHOST_kKeyUnknown) {
    return false;
  }
  const bool down = (event_type == EMSCRIPTEN_EVENT_KEYDOWN);
  if (!down && !pressed_keys_.contains(key)) return false;
  if (down) pressed_keys_.insert(key); else pressed_keys_.erase(key);

  switch (key) {
    case GHOST_kKeyLeftShift: modifiers_.set(GHOST_kModifierKeyLeftShift, down); break;
    case GHOST_kKeyRightShift: modifiers_.set(GHOST_kModifierKeyRightShift, down); break;
    case GHOST_kKeyLeftControl: modifiers_.set(GHOST_kModifierKeyLeftControl, down); break;
    case GHOST_kKeyRightControl: modifiers_.set(GHOST_kModifierKeyRightControl, down); break;
    case GHOST_kKeyLeftAlt: modifiers_.set(GHOST_kModifierKeyLeftAlt, down); break;
    case GHOST_kKeyRightAlt: modifiers_.set(GHOST_kModifierKeyRightAlt, down); break;
    case GHOST_kKeyLeftOS: modifiers_.set(GHOST_kModifierKeyLeftOS, down); break;
    case GHOST_kKeyRightOS: modifiers_.set(GHOST_kModifierKeyRightOS, down); break;
    default: break;
  }

  char utf8[6] = {0};
  const size_t length = strlen(e->key);
  const auto lead = static_cast<unsigned char>(e->key[0]);
  const size_t utf8_length = lead < 0x80 ? 1 : lead < 0xE0 ? 2 : lead < 0xF0 ? 3 : 4;
  if (down && length == utf8_length && length <= 4) memcpy(utf8, e->key, length);
  pushEvent(std::unique_ptr<const GHOST_IEvent>(new GHOST_EventKey(getMilliSeconds(),
                               down ? GHOST_kEventKeyDown : GHOST_kEventKeyUp,
                               window_,
                               key,
                               e->repeat,
                               utf8)));
  /* Let the browser keep F5/F11/devtools shortcuts etc. only when unhandled. */
  return true;
}

bool GHOST_SystemWeb::handleResize()
{
  double w = 0, h = 0;
  if (emscripten_get_element_css_size(WEB_CANVAS, &w, &h) != EMSCRIPTEN_RESULT_SUCCESS || w <= 0) {
    return false;
  }
  canvas_w_ = uint32_t(w);
  canvas_h_ = uint32_t(h);
  if (window_) {
    window_->resize(canvas_w_, canvas_h_);
    pushEvent(std::unique_ptr<const GHOST_IEvent>(new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowSize, window_)));
  }
  return true;
}

bool GHOST_SystemWeb::handleFocus()
{
  if (!window_) return false;
  window_manager_->setActiveWindow(window_);
  pushEvent(std::make_unique<GHOST_Event>(getMilliSeconds(), GHOST_kEventWindowActivate, window_));
  return false;
}

bool GHOST_SystemWeb::handleBlur()
{
  if (!window_) return false;
  for (auto key : pressed_keys_) {
    pushEvent(std::make_unique<GHOST_EventKey>(getMilliSeconds(), GHOST_kEventKeyUp, window_, key, false));
  }
  pressed_keys_.clear(); modifiers_.clear();
  window_manager_->setWindowInactive(window_);
  pushEvent(std::make_unique<GHOST_Event>(getMilliSeconds(), GHOST_kEventWindowDeactivate, window_));
  for (auto button : {GHOST_kButtonMaskLeft, GHOST_kButtonMaskMiddle, GHOST_kButtonMaskRight}) {
    if (buttons_.get(button)) pushEvent(std::make_unique<GHOST_EventButton>(
      getMilliSeconds(), GHOST_kEventButtonUp, window_, button, GHOST_TABLET_DATA_NONE));
  }
  buttons_.clear(); touch_id_ = -1;
  return false; // Allow normal browser focus navigation.
}

bool GHOST_SystemWeb::handleTouch(int type, const EmscriptenTouchEvent *event)
{
  if (!window_) return false;
  const EmscriptenTouchPoint *point = nullptr;
  for (int i = 0; i < event->numTouches; ++i) {
    const auto &candidate = event->touches[i];
    if (candidate.isChanged && (touch_id_ == -1 || candidate.identifier == touch_id_)) {
      point = &candidate; break;
    }
  }
  if (type == EMSCRIPTEN_EVENT_TOUCHCANCEL) {
    handleBlur(); return true;
  }
  if (!point) return false;
  if (type == EMSCRIPTEN_EVENT_TOUCHSTART) {
    if (touch_id_ != -1) return true;
    touch_id_ = point->identifier;
    MAIN_THREAD_EM_ASM({ Module.canvas.focus({preventScroll:true}); });
  } else if (touch_id_ == -1) return false;
  cursor_x_ = point->targetX; cursor_y_ = point->targetY;
  pushEvent(std::make_unique<GHOST_EventCursor>(getMilliSeconds(), GHOST_kEventCursorMove,
    window_, cursor_x_, cursor_y_, GHOST_TABLET_DATA_NONE));
  if (type == EMSCRIPTEN_EVENT_TOUCHSTART || type == EMSCRIPTEN_EVENT_TOUCHEND) {
    const bool down = type == EMSCRIPTEN_EVENT_TOUCHSTART;
    buttons_.set(GHOST_kButtonMaskLeft, down);
    pushEvent(std::make_unique<GHOST_EventButton>(getMilliSeconds(),
      down ? GHOST_kEventButtonDown : GHOST_kEventButtonUp, window_, GHOST_kButtonMaskLeft, GHOST_TABLET_DATA_NONE));
    if (!down) touch_id_ = -1;
  }
  return true;
}
