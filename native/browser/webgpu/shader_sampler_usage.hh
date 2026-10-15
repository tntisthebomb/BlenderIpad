/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <cctype>
#include <string>

namespace blender::gpu::webgpu_prepare {
/* Tint retains combined-sampler declarations for texelFetch and emits phony
 * `_ = sampler;` uses. Those do not sample or filter. Treat every other use
 * conservatively as a real use, including passing the handle to a helper. */
inline bool sampler_is_used(const std::string &wgsl, const std::string &name)
{
  auto identifier = [](char c) { return std::isalnum(static_cast<unsigned char>(c)) || c == '_'; };
  size_t at = 0;
  while ((at = wgsl.find(name, at)) != std::string::npos) {
    const size_t end = at + name.size();
    if ((at && identifier(wgsl[at - 1])) || (end < wgsl.size() && identifier(wgsl[end]))) {
      at = end;
      continue;
    }
    size_t before = at, after = end;
    while (before && std::isspace(static_cast<unsigned char>(wgsl[before - 1]))) --before;
    while (after < wgsl.size() && std::isspace(static_cast<unsigned char>(wgsl[after]))) ++after;
    const bool declaration = before >= 3 && wgsl.compare(before - 3, 3, "var") == 0 &&
                             (before == 3 || !identifier(wgsl[before - 4])) &&
                             after < wgsl.size() && wgsl[after] == ':';
    bool phony = false;
    if (before && wgsl[before - 1] == '=' && after < wgsl.size() && wgsl[after] == ';') {
      size_t lhs = before - 1;
      while (lhs && std::isspace(static_cast<unsigned char>(wgsl[lhs - 1]))) --lhs;
      phony = lhs && wgsl[lhs - 1] == '_' && (lhs == 1 || !identifier(wgsl[lhs - 2]));
    }
    if (!declaration && !phony) return true;
    at = end;
  }
  return false;
}
}  // namespace blender::gpu::webgpu_prepare
