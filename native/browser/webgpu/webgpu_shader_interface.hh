/* SPDX-FileCopyrightText: 2026 Blender Authors
 *
 * SPDX-License-Identifier: GPL-2.0-or-later */

/** \file
 * \ingroup gpu
 *
 * WebGPU shader interface. Built directly from the ShaderCreateInfo (like the
 * Vulkan backend) rather than by GL-style runtime introspection. Assigns a
 * single flat, unique binding number per resource within bind group 0 — the
 * SAME sequential scheme WebGPUShader::resources_declare uses for the GLSL
 * `layout(binding=)` qualifiers, so the WGSL `@group(0) @binding(N)` produced by
 * Tint matches the bindings the interface reports back to the GPU module.
 */

#pragma once

#include "gpu_shader_interface.hh"
#include <string>
#include <unordered_map>

namespace blender::gpu {

class WebGPUShaderInterface : public ShaderInterface {
 public:
  WebGPUShaderInterface() = default;
  ~WebGPUShaderInterface() override = default;

  void init(const shader::ShaderCreateInfo &info);

  const ShaderInput *ubo_get_by_wgsl_binding(uint32_t binding) const;
  const ShaderInput *ssbo_get_by_wgsl_binding(uint32_t binding) const;
  const ShaderInput *uniform_get_by_wgsl_binding(uint32_t binding) const;

  /* Canonical bind-group-0 binding for a resource, matching
   * WebGPUShader::resources_declare. Static so the GLSL generator can share it. */
  static int resource_binding(const shader::ShaderCreateInfo &info,
                              const shader::ShaderCreateInfo::Resource &res);

 private:
  /* Tint may rename block variables, so use the GLSL binding to recover the
   * original create-info name. Keep names rather than pointers: sort_inputs()
   * reorders the input array, and SSBO locations must remain Blender slots. */
  std::unordered_map<uint32_t, std::string> resource_names_;
  void populate_builtins(const shader::ShaderCreateInfo &info);
};

}  // namespace blender::gpu
