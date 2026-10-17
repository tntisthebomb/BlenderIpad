/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#ifdef __EMSCRIPTEN__
#  include <emscripten/emscripten.h>
#  include <emscripten/threading.h>
/* An early return INSIDE EM_ASYNC_JS still creates a Promise and suspends.
 * Decide synchronously so disabled / steady-state calls never enter Asyncify. */
EM_JS(int, blender_browser_startup_should_yield, (), {
  if (!Module['browserCooperativeStartup'] || Module['browserStartupComplete']) return 0;
  return performance.now() - (Module['browserLastStartupYield'] ?? -Infinity) >= 16 ? 1 : 0;
});
EM_ASYNC_JS(void, blender_browser_startup_yield, (), {
  Module['browserLastStartupYield'] = performance.now();
  Module['browserStartupYieldCount'] = (Module['browserStartupYieldCount'] ?? 0) + 1;
  Module['browserStartupSuspended'] = true;
  try { await new Promise(resolve => setTimeout(resolve, 0)); }
  finally { Module['browserStartupSuspended'] = false; }
});
static inline void blender_browser_startup_cooperate()
{
  if (blender_browser_startup_should_yield()) blender_browser_startup_yield();
}
#endif
