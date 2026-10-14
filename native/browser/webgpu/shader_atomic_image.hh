/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include "shader_prepare.hh"
#include <algorithm>
#include <stdexcept>
#include <unordered_map>

namespace blender::gpu::webgpu_prepare {

/* Baseline WebGPU has storage-buffer atomics, but no storage-texture atomics.
 * Preserve atomic image semantics in a padded buffer, synchronized with the
 * texture by WebGPUTexture. The first four words describe width/height/depth
 * and row stride in words; texel data starts at byte 16. */
inline std::string lower_atomic_images(const std::string &source)
{
  const auto ts = tokens(source);
  std::unordered_set<std::string> names;
  for (size_t i = 0; i + 3 < ts.size(); i++) {
    if (ts[i].text.rfind("imageAtomic", 0) == 0 && ts[i + 1].text == "(" &&
        ts[i + 3].text == ",") names.insert(ts[i + 2].text);
  }
  if (names.empty()) return source;
  struct Edit { size_t begin, end; std::string text; };
  std::vector<Edit> edits;
  std::unordered_set<std::string> declared;
  for (size_t i = 1; i + 1 < ts.size(); i++) {
    if (!names.count(ts[i].text) || ts[i + 1].text != ";") continue;
    const std::string type = ts[i - 1].text;
    if (type != "uimage2D" && type != "uimage2DArray" && type != "uimage3D" &&
        type != "iimage2D" && type != "iimage2DArray" && type != "iimage3D") continue;
    const auto &name = ts[i].text;
    const bool is_signed = type[0] == 'i';
    const bool is_2d = type == "uimage2D" || type == "iimage2D";
    size_t start = i - 1;
    while (start && ts[start].text != "layout" && ts[start - 1].text != ";" &&
           ts[start - 1].text != "}") start--;
    if (ts[start].text != "layout") throw std::runtime_error("atomic image layout missing");
    std::string binding, set = "0";
    bool format_ok = false;
    for (size_t j = start; j + 2 < i; j++) {
      if (ts[j].text == "binding" && ts[j + 1].text == "=") binding = ts[j + 2].text;
      if (ts[j].text == "set" && ts[j + 1].text == "=") set = ts[j + 2].text;
      if (ts[j].text == (is_signed ? "r32i" : "r32ui")) format_ok = true;
    }
    if (binding.empty() || !format_ok) throw std::runtime_error("atomic image requires R32I/R32UI");
    const std::string scalar = is_signed ? "int" : "uint";
    const std::string vector = is_signed ? "ivec4" : "uvec4";
    const std::string coord = is_2d ? "ivec2" : "ivec3";
    const std::string prefix = "wgpu_ai_" + name;
    const std::string block = "wgpu_atomic_image_" + name;
    const std::string data = prefix + "_data";
    const std::string meta = prefix + "_meta";
    std::string out = "layout(set=" + set + ",binding=" + binding + ",std430) buffer _" +
        block + " { uvec4 " + meta + "; " + scalar + " " + data + "[]; };\n";
    out += "uint " + prefix + "_index(" + coord + " p) { ivec3 q=" +
        (is_2d ? "ivec3(p,0)" : "p") + "; if(any(lessThan(q,ivec3(0))) || "
        "any(greaterThanEqual(uvec3(q)," + meta + ".xyz))) return 0xffffffffu; "
        "return (uint(q.z)*" + meta + ".y+uint(q.y))*" + meta + ".w+uint(q.x); }\n";
    const std::pair<const char *, const char *> ops[] = {
        {"Add","atomicAdd"}, {"Min","atomicMin"}, {"Max","atomicMax"},
        {"And","atomicAnd"}, {"Or","atomicOr"}, {"Xor","atomicXor"},
        {"Exchange","atomicExchange"}, {"CompSwap","atomicCompSwap"}};
    for (const auto &op : ops) {
      const bool compare = std::string(op.first) == "CompSwap";
      out += scalar + " " + prefix + "_imageAtomic" + op.first + "(" + coord + " p," +
          scalar + " v" + (compare ? "," + scalar + " replacement" : "") + ") { uint i=" +
          prefix + "_index(p); if(i==0xffffffffu) return " + scalar + "(0); return " +
          op.second + "(" + data + "[i],v" + (compare ? ",replacement" : "") + "); }\n";
    }
    out += vector + " " + prefix + "_imageLoad(" + coord + " p) { uint i=" + prefix +
        "_index(p); return " + vector + "(i==0xffffffffu ? " + scalar + "(0) : " + data +
        "[i],0,0,0); }\n";
    out += "void " + prefix + "_imageStore(" + coord + " p," + vector + " v) { uint i=" +
        prefix + "_index(p); if(i!=0xffffffffu) atomicExchange(" + data + "[i],v.x); }\n";
    out += coord + " " + prefix + "_imageSize() { return " + coord + "(" + meta +
        (is_2d ? ".xy" : ".xyz") + "); }\n";
    edits.push_back({ts[start].begin, ts[i + 1].end, out});
    declared.insert(name);
  }
  for (const auto &name : names) {
    if (!declared.count(name)) throw std::runtime_error("unsupported atomic image handle: " + name);
  }
  for (size_t i = 0; i + 3 < ts.size(); i++) {
    if (ts[i + 1].text != "(" || !declared.count(ts[i + 2].text)) continue;
    const auto &op = ts[i].text;
    if (op.rfind("imageAtomic", 0) != 0 && op != "imageLoad" && op != "imageStore" &&
        op != "imageSize") continue;
    if (ts[i + 3].text != "," && ts[i + 3].text != ")") continue;
    edits.push_back({ts[i].begin, ts[i + 3].end,
                     "wgpu_ai_" + ts[i + 2].text + "_" + op +
                     (ts[i + 3].text == ")" ? "()" : "(")});
  }
  std::sort(edits.begin(), edits.end(), [](const Edit &a, const Edit &b) {
    return a.begin > b.begin;
  });
  std::string result = source;
  for (const auto &edit : edits) result.replace(edit.begin, edit.end - edit.begin, edit.text);
  return result;
}

}  // namespace blender::gpu::webgpu_prepare
