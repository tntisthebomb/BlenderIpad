/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#ifdef __EMSCRIPTEN__
#  include <emscripten/threading.h>
EM_ASYNC_JS(void, blender_browser_startup_yield, (), {
  if (!Module['browserCooperativeStartup'] || Module['browserStartupComplete']) return;
  const now = performance.now();
  if (now - (Module['browserLastStartupYield'] ?? -Infinity) < 16) return;
  Module['browserLastStartupYield'] = now;
  Module['browserStartupYieldCount'] = (Module['browserStartupYieldCount'] ?? 0) + 1;
  Module['browserStartupSuspended'] = true;
  try { await new Promise(resolve => setTimeout(resolve, 0)); }
  finally { Module['browserStartupSuspended'] = false; }
});
#endif
