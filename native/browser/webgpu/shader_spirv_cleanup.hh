/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <spirv-tools/optimizer.hpp>
#include <stdexcept>
#include <vector>

namespace blender::gpu::webgpu_prepare {
/* Shaderc retains resources in unreachable helper functions. Reflecting those
 * declarations creates layouts exceeding real device limits. Remove dead code
 * without the broad performance optimizer's CFG rewrites or floating-point
 * folding, which expose unsupported Tint paths. Preserve names used to identify
 * push constants and resource blocks. */
inline void remove_dead_resources(std::vector<uint32_t> &words)
{
  spvtools::Optimizer optimizer(SPV_ENV_VULKAN_1_0);
  optimizer.RegisterPass(spvtools::CreateDeadBranchElimPass());
  optimizer.RegisterPass(spvtools::CreateEliminateDeadFunctionsPass());
  optimizer.RegisterPass(spvtools::CreateAggressiveDCEPass());
  optimizer.RegisterPass(spvtools::CreateDeadVariableEliminationPass());
  std::vector<uint32_t> result;
  if(!optimizer.Run(words.data(),words.size(),&result)) {
    throw std::runtime_error("SPIR-V dead resource elimination failed");
  }
  words=std::move(result);
}
}
