/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#include "src/tint/lang/core/ir/module.h"
#include "src/tint/lang/spirv/reader/reader.h"
#include "src/tint/lang/wgsl/reader/reader.h"
#include "src/tint/lang/wgsl/writer/writer.h"

int main(int argc, char **argv)
{
  try {
    if (argc != 3) throw std::runtime_error("expected SPIR-V input and WGSL output paths");
    std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
    if (!file) throw std::runtime_error("SPIR-V input missing");
    const auto bytes = file.tellg();
    if (bytes <= 0 || bytes % 4) throw std::runtime_error("invalid SPIR-V input size");
    std::vector<uint32_t> words(size_t(bytes) / 4);
    file.seekg(0);
    file.read(reinterpret_cast<char *>(words.data()), bytes);
    if (!file) throw std::runtime_error("SPIR-V input read failed");
    tint::spirv::reader::Options reader_options;
    // Match the application's stable texture/sampler binding pairs. Tint's
    // default mapping can renumber subsequent resources when splitting them.
    for (uint32_t binding = 0; binding < 128; ++binding) {
      reader_options.sampler_mappings.insert(
          {tint::BindingPoint{0, binding}, tint::BindingPoint{0, binding + 128}});
    }
    auto ir = tint::spirv::reader::ReadIR(words, reader_options);
    if (ir != tint::Success) throw std::runtime_error(ir.Failure().reason);
    auto wgsl = tint::wgsl::writer::WgslFromIR(ir.Get(), {});
    if (wgsl != tint::Success) throw std::runtime_error(wgsl.Failure().reason);
    tint::Source::File source("blender-matrix.wgsl", wgsl.Get().wgsl);
    auto parsed = tint::wgsl::reader::Parse(&source);
    if (!parsed.IsValid()) throw std::runtime_error(parsed.Diagnostics().Str());
    std::ofstream output(argv[2]);
    output << wgsl.Get().wgsl;
    if (!output) throw std::runtime_error("WGSL output write failed");
    auto invalid = words;
    invalid[0] = 0;
    if (tint::spirv::reader::ReadIR(invalid, reader_options) == tint::Success)
      throw std::runtime_error("invalid SPIR-V was accepted");
    tint::Source::File bad("invalid.wgsl", "@compute fn main( {");
    if (tint::wgsl::reader::Parse(&bad).IsValid())
      throw std::runtime_error("invalid WGSL was accepted");
    std::cout << "PASS: SPIR-V translated to valid WGSL; invalid inputs rejected.\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
