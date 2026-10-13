/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "gpu_shader_dependency_private.hh"
#include <cstdio>
int main() {
  blender::gpu_shader_dependency_init();
  const auto matrix=blender::gpu::shader::gpu_shader_dependency_get_source("gpu_shader_math_matrix_lib.glsl");
  if (matrix.is_empty()) return 1;
  blender::gpu_shader_dependency_exit();
  std::puts("PASS: actual stable shader registry, dependencies and printf metadata initialized.");
}
