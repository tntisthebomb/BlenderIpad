/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include "src/tint/lang/core/ir/function.h"
#include "src/tint/lang/core/ir/module.h"
#include "src/tint/lang/core/ir/return.h"
#include "src/tint/lang/core/ir/user_call.h"
#include "src/tint/lang/core/type/sampler.h"
#include "src/tint/utils/containers/vector.h"

namespace blender::gpu::webgpu_prepare {
/* SPIR-V combined samplers become separate texture/sampler parameters. A
 * texelFetch helper can retain the sampler parameter even though its body never
 * uses it. Remove only parameters with no IR uses, together with their call
 * arguments, so WGSL reflection can distinguish loads from actual sampling.
 * Repeat to propagate the removal through forwarding helpers. */
inline void remove_unused_sampler_parameters(tint::core::ir::Module &module)
{
  bool changed;
  do {
    changed = false;
    for (auto &function : module.functions) {
      if (function->IsEntryPoint()) {
        continue;
      }
      tint::Vector<tint::core::ir::FunctionParam *, 8> parameters;
      tint::Vector<size_t, 8> retained;
      const auto original = function->Params();
      for (size_t i = 0; i < original.Length(); ++i) {
        auto *parameter = original[i];
        if (!parameter->Type()->Is<tint::core::type::Sampler>() || parameter->NumUsages()) {
          parameters.Push(parameter);
          retained.Push(i);
        }
      }
      if (parameters.Length() == original.Length()) {
        continue;
      }
      tint::Vector<tint::core::ir::UserCall *, 8> calls;
      bool supported = true;
      function->ForEachUseUnsorted([&](tint::core::ir::Usage use) {
        /* Return records its owning function as operand zero. This is not a
         * call argument and does not depend on the parameter list. */
        if (use.operand_index == 0 && use.instruction->Is<tint::core::ir::Return>()) {
          return;
        }
        auto *call = use.instruction->As<tint::core::ir::UserCall>();
        if (!call || use.operand_index != 0 || call->Args().Length() != original.Length()) {
          supported = false;
        }
        else {
          calls.Push(call);
        }
      });
      if (!supported) {
        continue;
      }
      for (auto *call : calls) {
        tint::Vector<tint::core::ir::Value *, 8> arguments;
        for (size_t index : retained) {
          arguments.Push(call->Args()[index]);
        }
        call->SetArgs(arguments);
      }
      function->SetParams(parameters);
      changed = true;
    }
  } while (changed);
}
}  // namespace blender::gpu::webgpu_prepare
