/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "GPU_context.hh"
#include "GPU_init_exit.hh"
#include "CLG_log.h"
#include "gpu_shader_create_info.hh"
#include "webgpu/webgpu_shader_interface.hh"
#include <cassert>
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
  {
    using namespace gpu;
    using namespace gpu::shader;
    ShaderCreateInfo info("binding_mapping_regression");
    info.uniform_buf(3, "vec4", "original_uniform");
    info.storage_buf(7, Qualifier::read, "uint", "original_storage[]");
    info.sampler(5, ImageType::Float2D, "original_texture");
    info.storage_buf(8, Qualifier::read, "uint", "other_storage[]", Frequency::BATCH);
    info.push_constant(Type::float_t, "push_value");
    WebGPUShaderInterface interface;
    interface.init(info);
    assert(interface.ubo_get_by_wgsl_binding(0)->binding == 3);
    assert(interface.ssbo_get_by_wgsl_binding(1)->binding == 7);
    assert(interface.ssbo_get_by_wgsl_binding(1)->location == 7);
    assert(interface.uniform_get_by_wgsl_binding(2)->binding == 5);
    assert(interface.ssbo_get_by_wgsl_binding(3)->binding == 8);
    assert(interface.uniform_get_by_wgsl_binding(0) == nullptr);
    assert(interface.ubo_get_by_wgsl_binding(99) == nullptr);
    std::puts("Shader binding mapping preserves native slots, array names and resource types.");
  }
  GPU_exit();
  GPU_context_discard(context);
  CLG_exit();
  EM_ASM({ document.body.dataset.done = 'true'; });
}
