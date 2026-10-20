/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "GPU_context.hh"
#include "GPU_init_exit.hh"
#include "GPU_framebuffer.hh"
#include "GPU_texture.hh"
#include "CLG_log.h"
#include "gpu_shader_create_info.hh"
#include "webgpu/webgpu_shader_interface.hh"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cmath>
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
  /* These are the real framebuffer APIs used by viewport and gizmo picking.
   * The previous backend rejected UINT depth and emitted an invalid WebGPU
   * texture copy for every offset/subrectangle FLOAT depth request. */
  for (const auto format : {gpu::TextureFormat::SFLOAT_32_DEPTH,
                            gpu::TextureFormat::SFLOAT_32_DEPTH_UINT_8}) {
    gpu::Texture *depth = GPU_texture_create_2d("pick_depth", 13, 9, 1, format,
                                               GPU_TEXTURE_USAGE_GENERAL, nullptr);
    assert(depth);
    gpu::FrameBuffer *fb = nullptr;
    GPU_framebuffer_ensure_config(&fb, {GPU_ATTACHMENT_TEXTURE(depth)});
    GPU_framebuffer_bind(fb);
    for (const float clear_depth : {0.0f, 0.375f, 1.0f}) {
      GPU_framebuffer_clear_depth(fb, clear_depth);
      float floats[6] = {-1, -1, -1, -1, -1, -1};
      GPU_framebuffer_read_depth(fb, 4, 3, 3, 2, GPU_DATA_FLOAT, floats);
      for (const float value : floats) assert(std::fabs(value - clear_depth) < 1e-6f);
      uint32_t integers[6] = {};
      GPU_framebuffer_read_depth(fb, 4, 3, 3, 2, GPU_DATA_UINT, integers);
      for (const uint32_t value : integers) {
        const uint32_t expected = uint32_t(double(clear_depth) * double(UINT32_MAX));
        assert(value == expected);
      }
      /* The last pixel exercises row padding and the far edge of the crop. */
      float edge = -1.0f;
      GPU_framebuffer_read_depth(fb, 12, 8, 1, 1, GPU_DATA_FLOAT, &edge);
      assert(std::fabs(edge - clear_depth) < 1e-6f);
    }
    GPU_framebuffer_restore();
    GPU_framebuffer_free(fb);
    GPU_texture_free(depth);
  }
  std::puts("Actual viewport picking depth reads pass for FLOAT and UINT subrectangles.");
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
