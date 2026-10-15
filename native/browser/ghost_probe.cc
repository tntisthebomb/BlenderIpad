/* SPDX-License-Identifier: GPL-2.0-or-later */
// A development probe for the actual GHOST factory and event queue, not Blender's UI.
#include "GHOST_ISystem.hh"
#include "GHOST_CallbackEventConsumer.hh"
#include "GHOST_SystemWeb.hh"
#include "CLG_log.h"
#include <cstdio>
#include <cstring>

static GHOST_ISystem *system_instance;
static GHOST_IWindow *window_instance;
static GHOST_CallbackEventConsumer *consumer;
static int key_down, key_up, mouse_down, mouse_up, cursor_moves, wheel, resizes, redraws;
static int last_key, repeat, width, height;
static int trackpad_pan, trackpad_zoom, pan_x, pan_y, zoom_x;
static char last_text[6];

static bool consume(const GHOST_IEvent *event, void *)
{
  if (!system_instance->validWindow(event->getWindow())) return false;
  switch (event->getType()) {
    case GHOST_kEventKeyDown:
    case GHOST_kEventKeyUp: {
      const auto *data = static_cast<const GHOST_TEventKeyData *>(event->getData());
      if (event->getType() == GHOST_kEventKeyDown) ++key_down; else ++key_up;
      last_key = data->key; repeat = data->is_repeat;
      memcpy(last_text, data->utf8_buf, sizeof(last_text));
      break;
    }
    case GHOST_kEventButtonDown: ++mouse_down; break;
    case GHOST_kEventButtonUp: ++mouse_up; break;
    case GHOST_kEventCursorMove: ++cursor_moves; break;
    case GHOST_kEventWheel: ++wheel; break;
    case GHOST_kEventTrackpad: {
      const auto *data = static_cast<const GHOST_TEventTrackpadData *>(event->getData());
      if (data->subtype == GHOST_kTrackpadEventScroll) {
        ++trackpad_pan; pan_x += data->deltaX; pan_y += data->deltaY;
      }
      if (data->subtype == GHOST_kTrackpadEventMagnify) {
        ++trackpad_zoom; zoom_x += data->deltaX;
      }
      break;
    }
    case GHOST_kEventWindowSize: {
      ++resizes;
      GHOST_Rect bounds;
      event->getWindow()->getClientBounds(bounds);
      width = bounds.getWidth(); height = bounds.getHeight();
      break;
    }
    case GHOST_kEventWindowUpdate: ++redraws; break;
    default: break;
  }
  return true;
}

extern "C" {
int ghost_probe_init()
{
  if (system_instance) return 0;
  CLG_init();
  if (GHOST_ISystem::createSystem(true, false) != GHOST_kSuccess) return 0;
  system_instance = GHOST_ISystem::getSystem();
  consumer = new GHOST_CallbackEventConsumer(consume, nullptr);
  system_instance->addEventConsumer(consumer);
  GHOST_GPUSettings settings = {};
  settings.context_type = GHOST_kDrawingContextTypeNone;
  window_instance = system_instance->createWindow("Blender 5.2.2 native GHOST port", 0, 0,
      800, 450, GHOST_kWindowStateNormal, settings, false, false, nullptr);
  return window_instance && system_instance->validWindow(window_instance);
}
void ghost_probe_tick()
{
  if (!system_instance) return;
  system_instance->processEvents(false);
  system_instance->dispatchEvents();
}
const char *ghost_probe_snapshot()
{
  static char output[768];
  GHOST_ModifierKeys keys;
  GHOST_Buttons buttons;
  if (system_instance) {
    auto *web_system = static_cast<GHOST_SystemWeb *>(system_instance);
    web_system->getModifierKeys(keys); web_system->getButtons(buttons);
  }
  snprintf(output, sizeof(output),
    "{\"keydown\":%d,\"keyup\":%d,\"mousedown\":%d,\"mouseup\":%d,\"cursor\":%d,"
    "\"wheel\":%d,\"resizes\":%d,\"redraws\":%d,\"key\":%d,\"repeat\":%d,\"width\":%d,\"height\":%d,"
    "\"left_shift\":%d,\"right_shift\":%d,\"left_button\":%d,\"backend\":\"%s\","
    "\"trackpad_pan\":%d,\"trackpad_zoom\":%d,\"pan_x\":%d,\"pan_y\":%d,\"zoom_x\":%d}",
    key_down,key_up,mouse_down,mouse_up,cursor_moves,wheel,resizes,redraws,last_key,repeat,width,height,
    keys.get(GHOST_kModifierKeyLeftShift), keys.get(GHOST_kModifierKeyRightShift),
    buttons.get(GHOST_kButtonMaskLeft), system_instance ? GHOST_ISystem::getSystemBackend() : "none",
    trackpad_pan, trackpad_zoom, pan_x, pan_y, zoom_x);
  return output;
}
int ghost_probe_key_g() { return int(GHOST_kKeyG); }
const char *ghost_probe_text() { return last_text; }
void ghost_probe_redraw() { if (window_instance) window_instance->invalidate(); }
void ghost_probe_close_window()
{
  if (window_instance) { system_instance->disposeWindow(window_instance); window_instance = nullptr; }
}
int ghost_probe_reopen_window()
{
  if (!system_instance || window_instance) return 0;
  GHOST_GPUSettings settings = {};
  settings.context_type = GHOST_kDrawingContextTypeNone;
  window_instance = system_instance->createWindow("Blender 5.2.2 native GHOST port", 0, 0,
      800, 450, GHOST_kWindowStateNormal, settings, false, false, nullptr);
  return window_instance && system_instance->validWindow(window_instance);
}
void ghost_probe_shutdown()
{
  if (!system_instance) return;
  ghost_probe_close_window();
  system_instance->removeEventConsumer(consumer); delete consumer; consumer = nullptr;
  GHOST_ISystem::disposeSystem(); system_instance = nullptr;
  CLG_exit();
}
}
