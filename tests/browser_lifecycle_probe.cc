#include <emscripten.h>

static int ticks;
static void frame() { ticks++; }
extern "C" int lifecycle_ticks() { return ticks; }
__attribute__((destructor)) static void finalized()
{
  EM_ASM({ Module.destructorRan = true; });
}
int main()
{
  emscripten_set_main_loop(frame, 0, false);
  return 0;
}
