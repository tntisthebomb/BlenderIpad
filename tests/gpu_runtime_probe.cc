/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "GPU_context.hh"
#include "GPU_init_exit.hh"
#include "CLG_log.h"
#include <cstdio>
#include <cstdlib>
#include <emscripten.h>
int main()
{
  using namespace blender;
  CLG_init();
  setenv("BLENDER_GPU_INIT_TRACE", "1", 1);
  GPU_backend_type_selection_set(GPU_BACKEND_WEBGPU);
  GPUContext *context = GPU_context_create(nullptr, nullptr);
  std::puts("Real Blender GPU context created; entering GPU_init.");
  GPU_init();
  std::puts("Actual Blender GPU registration and builtin warm-up completed.");
  GPU_exit();
  GPU_context_discard(context);
  CLG_exit();
  EM_ASM({ document.body.dataset.done = 'true'; });
}
