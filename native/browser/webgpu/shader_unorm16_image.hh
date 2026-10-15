/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include "shader_prepare.hh"
#include <algorithm>
#include <stdexcept>
#include <unordered_map>

namespace blender::gpu::webgpu_prepare {

/* Baseline WebGPU has no 16-bit normalized storage images. Keep their exact
 * normalized values in float32 texels, including clamping and quantization on
 * every store. Half floats cannot represent all 65,536 normalized values. */
inline std::string lower_unorm16_images(const std::string &source)
{
  const auto ts = tokens(source);
  struct Edit { size_t begin, end; std::string text; };
  std::vector<Edit> edits;
  std::unordered_map<std::string, std::string> stores;
  for (size_t i = 1; i + 1 < ts.size(); i++) {
    if (ts[i + 1].text != ";") continue;
    const auto &type = ts[i - 1].text;
    if (type != "image2D" && type != "image2DArray" && type != "image3D") continue;
    size_t start = i - 1;
    while (start && ts[start].text != "layout" && ts[start - 1].text != ";" &&
           ts[start - 1].text != "}") start--;
    if (ts[start].text != "layout") continue;
    for (size_t j = start; j < i; j++) {
      const auto &format = ts[j].text;
      const int channels = format == "r16" ? 1 : format == "rg16" ? 2 :
                           format == "rgba16" || format == "rgb10_a2" ? 4 : 0;
      if (!channels) continue;
      edits.push_back({ts[j].begin, ts[j].end, "rgba32f"});
      const auto &name = ts[i].text;
      const std::string helper = "wgpu_unorm16_store_" + name;
      stores[name] = helper;
      const bool readonly_image = std::any_of(ts.begin() + start, ts.begin() + i,
          [](const Token &token) { return token.text == "readonly"; });
      if (!readonly_image) {
        const std::string coord = type == "image2D" ? "ivec2" : "ivec3";
        const std::string value = channels == 1 ? "vec4(q.x,0,0,1)" :
                                  channels == 2 ? "vec4(q.xy,0,1)" : "q";
        const std::string scale = format == "rgb10_a2" ? "vec4(1023,1023,1023,3)" : "vec4(65535)";
        edits.push_back({ts[i + 1].end, ts[i + 1].end,
            "\nvoid " + helper + "(" + coord + " p,vec4 v) { vec4 q="
            "round(clamp(v,vec4(0),vec4(1))*" + scale + ")/" + scale + "; imageStore(" +
            name + ",p," + value + "); }\n"});
      }
      break;
    }
  }
  for (size_t i = 0; i + 3 < ts.size(); i++) {
    if (ts[i].text != "imageStore" || ts[i + 1].text != "(" || ts[i + 3].text != ",") continue;
    const auto found = stores.find(ts[i + 2].text);
    if (found != stores.end()) {
      edits.push_back({ts[i].begin, ts[i + 3].end, found->second + "("});
    }
  }
  std::sort(edits.begin(), edits.end(), [](const Edit &a, const Edit &b) {
    return a.begin > b.begin;
  });
  std::string result = source;
  for (const auto &edit : edits) result.replace(edit.begin, edit.end - edit.begin, edit.text);
  return result;
}

}  // namespace blender::gpu::webgpu_prepare
