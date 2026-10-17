/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "webgpu/startup_yield.hh"
#include <emscripten.h>
#include <array>
int main()
{
  std::array<int,128> values{};
  EM_ASM({Module.startTick=window.ticks;Module.startPaint=window.paints;});
  for(int i=0;i<128;i++){
    const double end=emscripten_get_now()+2;
    while(emscripten_get_now()<end){}
    values[i]=i*i;
    blender_browser_startup_yield();
    for(int j=0;j<=i;j++)if(values[j]!=j*j)return 1;
  }
  EM_ASM({
    const count=Module.browserStartupYieldCount;
    if(count<2||window.ticks-Module.startTick<2||window.paints-Module.startPaint<1)throw Error('Browser did not get timer/paint opportunities');
    Module.savedYieldCount=count;Module.browserStartupComplete=true;
  });
  for(int i=0;i<128;i++)blender_browser_startup_yield();
  EM_ASM({
    if(Module.browserStartupYieldCount!==Module.savedYieldCount)throw Error('Startup yielding continued in steady editor');
    window.yieldProbeResult=({yields:Module.savedYieldCount,timerTicks:window.ticks-Module.startTick,paintTicks:window.paints-Module.startPaint});
    document.body.dataset.done='true';
  });
  return 0;
}
