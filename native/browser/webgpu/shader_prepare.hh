/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once

#include <cctype>
#include <cstdint>
#include <string>
#include <unordered_set>
#include <vector>

namespace blender::gpu::webgpu_prepare {

struct Token {
  std::string text;
  size_t begin, end;
};

/* Input has already passed shaderc's preprocessor. Ignore remaining #line
 * directives and quoted filenames rather than interpreting their punctuation. */
inline std::vector<Token> tokens(const std::string &source)
{
  std::vector<Token> result;
  for (size_t i = 0; i < source.size();) {
    const unsigned char c = source[i];
    if (std::isspace(c)) { i++; continue; }
    if (c == '#') {
      while (i < source.size() && source[i] != '\n') i++;
      continue;
    }
    const size_t start = i++;
    if (c == '"' || c == '\'') {
      while (i < source.size()) {
        if (source[i++] == char(c)) break;
        if (source[i - 1] == '\\' && i < source.size()) i++;
      }
    }
    else if (std::isalnum(c) || c == '_') {
      while (i < source.size() &&
             (std::isalnum(static_cast<unsigned char>(source[i])) || source[i] == '_')) i++;
    }
    result.push_back({source.substr(start, i - start), start, i});
  }
  return result;
}

inline size_t closing(const std::vector<Token> &ts, size_t open,
                      const char *left, const char *right)
{
  int depth = 0;
  for (size_t i = open; i < ts.size(); i++) {
    if (ts[i].text == left) depth++;
    if (ts[i].text == right) {
      depth--;
      if (depth == 0) return i;
    }
  }
  return ts.size();
}

inline bool terminates_case(const std::string &body)
{
  auto ts = tokens(body);
  size_t first = 0, last = ts.size();
  while (first < last && ts[first].text == "{" &&
         closing(ts, first, "{", "}") == last - 1) {
    first++; last--;
  }
  int depth = 0;
  for (size_t i = first; i < last; i++) {
    if (ts[i].text == "{") depth++;
    if (ts[i].text == "}") depth--;
    if (depth == 0 && (i == first || ts[i - 1].text == ";" || ts[i - 1].text == "}") &&
        (ts[i].text == "break" || ts[i].text == "return" || ts[i].text == "discard")) {
      return true;
    }
  }
  return false;
}

/* Duplicate a fallthrough tail in GLSL, before glslang assigns SSA IDs. The
 * pinned Tint reader cannot safely duplicate SPIR-V blocks containing phi
 * values. A normal switch break/return still exits before any copied tail;
 * loop-local breaks and conditional breaks do not truncate the tail. */
inline std::string lower_switches(const std::string &source)
{
  const auto ts = tokens(source);
  for (size_t i = 0; i + 1 < ts.size(); i++) {
    if (ts[i].text != "switch" || ts[i + 1].text != "(") continue;
    const size_t condition_end = closing(ts, i + 1, "(", ")");
    const size_t open = condition_end + 1;
    if (open >= ts.size() || ts[open].text != "{") return source;
    const size_t close = closing(ts, open, "{", "}");
    if (close >= ts.size()) return source;
    const std::string body = lower_switches(source.substr(ts[open].end,
                                                        ts[close].begin - ts[open].end));
    const auto inner = tokens(body);
    struct Case { size_t label, colon; };
    std::vector<Case> cases;
    int depth = 0;
    for (size_t j = 0; j < inner.size(); j++) {
      if (inner[j].text == "{") depth++;
      if (inner[j].text == "}") depth--;
      if (depth != 0 || (inner[j].text != "case" && inner[j].text != "default")) continue;
      int nesting = 0, ternary = 0;
      size_t colon = j + 1;
      for (; colon < inner.size(); colon++) {
        const auto &v = inner[colon].text;
        if (v == "(" || v == "[") nesting++;
        if (v == ")" || v == "]") nesting--;
        if (v == "?") ternary++;
        if (v == ":") {
          if (ternary) ternary--;
          else if (nesting == 0) break;
        }
      }
      if (colon == inner.size()) return source;
      cases.push_back({j, colon}); j = colon;
    }
    std::string lowered;
    if (!cases.empty()) lowered = body.substr(0, inner[cases.front().label].begin);
    else lowered = body;
    for (size_t c = 0; c < cases.size(); c++) {
      const auto &entry = cases[c];
      lowered += body.substr(inner[entry.label].begin,
                             inner[entry.colon].end - inner[entry.label].begin) + " {\n";
      for (size_t tail = c; tail < cases.size(); tail++) {
        const size_t begin = inner[cases[tail].colon].end;
        const size_t end = tail + 1 == cases.size() ? body.size() :
                          inner[cases[tail + 1].label].begin;
        const std::string statements = body.substr(begin, end - begin);
        lowered += statements;
        if (terminates_case(statements)) break;
      }
      lowered += "\nbreak;\n}\n";
    }
    return source.substr(0, ts[open].end) + lowered + "}" +
           lower_switches(source.substr(ts[close].end));
  }
  return source;
}

/* Preserve resource/interface names used by Blender's binding reflection, but
 * let Tint assign unique names to local values and overloaded functions.
 * Block type names also identify buffers in Blender's WGSL reflection.
 * Debug OpName strings are not scoped like WGSL declarations. */
inline void unique_local_names(std::vector<uint32_t> &words)
{
  if (words.size() < 5 || words[0] != 0x07230203) return;
  std::unordered_set<uint32_t> preserve;
  for (size_t i = 5; i < words.size();) {
    const uint32_t count = words[i] >> 16, op = words[i] & 0xffff;
    if (!count || i + count > words.size()) return;
    if (op == 15 && count >= 3) preserve.insert(words[i + 2]); /* OpEntryPoint */
    if (op == 71 && count >= 3 && (words[i + 2] == 2 || words[i + 2] == 3)) {
      preserve.insert(words[i + 1]); /* Block / BufferBlock type. */
    }
    if (op >= 48 && op <= 52 && count >= 3) preserve.insert(words[i + 2]); /* Specialization */
    if (op == 59 && count >= 4 && words[i + 3] != 7) { /* Non-function OpVariable */
      preserve.insert(words[i + 2]);
    }
    i += count;
  }
  std::vector<uint32_t> result(words.begin(), words.begin() + 5);
  for (size_t i = 5; i < words.size();) {
    const uint32_t count = words[i] >> 16, op = words[i] & 0xffff;
    if (op != 5 || count < 2 || preserve.count(words[i + 1])) {
      result.insert(result.end(), words.begin() + i, words.begin() + i + count);
    }
    i += count;
  }
  words.swap(result);
}

}  // namespace blender::gpu::webgpu_prepare
