/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "BLI_string_ref.hh"
#include <string>
#include <cstdio>
using blender::StringRef;
static_assert(sizeof(size_t)==4);
static_assert(StringRef("clean",5).find("//")==StringRef::not_found);
static_assert(StringRef("// comment",10).find("//")==0);
static_assert(StringRef("/* comment */",13).find("/*")==0);
static_assert(StringRef("clean",5).find("//")!=std::string::npos);
int main() {
  std::puts("PASS: wasm32 StringRef absence and real comment detection; std::string sentinel is incompatible.");
}
