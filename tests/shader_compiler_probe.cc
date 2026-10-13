/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <shaderc/shaderc.hpp>
#include <spirv-tools/libspirv.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <vector>

static std::string read_file(const std::filesystem::path &path)
{
  std::ifstream file(path, std::ios::binary);
  if (!file) throw std::runtime_error("missing shader input: " + path.string());
  std::ostringstream text;
  text << file.rdbuf();
  return text.str();
}

class Includes : public shaderc::CompileOptions::IncluderInterface {
  struct Item {
    shaderc_include_result result{};
    std::string name, text;
  };
  std::unordered_map<std::string, std::string> sources;
 public:
  Includes(const std::filesystem::path &source, const std::filesystem::path &generated)
  {
    sources["gpu_shader_compat_glsl.glsl"] = read_file(source / "gpu_shader_compat_glsl.glsl");
    sources["gpu_shader_math_matrix_lib.glsl"] = read_file(generated / "common/gpu_shader_math_matrix_lib.glsl.tmp");
    sources["gpu_shader_utildefines_lib.glsl"] = read_file(generated / "common/gpu_shader_utildefines_lib.glsl.tmp");
    // Blender generates the version/extension header at runtime. This probe
    // supplies its Vulkan 1.0 compute version in the top-level shader instead.
    sources["gpu_shader_glsl_extension.glsl"] = "";
  }
  shaderc_include_result *GetInclude(const char *name, shaderc_include_type,
                                    const char *, size_t) override
  {
    auto item = std::make_unique<Item>();
    const auto found = sources.find(name);
    item->name = name;
    item->text = found == sources.end() ? "#error Unsupported probe include\n" : found->second;
    item->result.source_name = item->name.c_str();
    item->result.source_name_length = item->name.size();
    item->result.content = item->text.c_str();
    item->result.content_length = item->text.size();
    item->result.user_data = item.get();
    return &item.release()->result;
  }
  void ReleaseInclude(shaderc_include_result *result) override
  {
    delete static_cast<Item *>(result->user_data);
  }
};

int main(int argc, char **argv)
{
  try {
    if (argc != 4 && argc != 5) throw std::runtime_error("expected source, generated, output and optional shader paths");
    shaderc::Compiler compiler;
    shaderc::CompileOptions options;
    options.SetTargetEnvironment(shaderc_target_env_vulkan, shaderc_env_version_vulkan_1_0);
    options.SetIncluder(std::make_unique<Includes>(argv[1], argv[2]));
    const std::string compute = argc == 5 ? read_file(argv[4]) : R"glsl(#version 450
#define GPU_VULKAN
#define GPU_COMPUTE_SHADER
#include "gpu_shader_compat_glsl.glsl"
#include "gpu_shader_math_matrix_lib.glsl"
layout(local_size_x=1) in;
layout(set=0, binding=0, std430) buffer Results { vec4 values[]; } output_data;
layout(set=0, binding=1, std430) readonly buffer Input { mat4 matrix; } input_data;
void main() {
  bool success;
  float4x4 inverse_matrix = invert(input_data.matrix, success);
  for (int column = 0; column < 4; column++) {
    output_data.values[column] = inverse_matrix[column];
  }
  output_data.values[4] = float4(success ? 1.0f : 0.0f);
}
)glsl";
    const auto result = compiler.CompileGlslToSpv(compute, shaderc_compute_shader,
                                               "blender-matrix.comp", options);
    if (result.GetCompilationStatus() != shaderc_compilation_status_success)
      throw std::runtime_error(result.GetErrorMessage());
    const std::vector<uint32_t> words(result.cbegin(), result.cend());
    spvtools::SpirvTools validator(SPV_ENV_VULKAN_1_0);
    validator.SetMessageConsumer([](spv_message_level_t, const char *, const spv_position_t &,
                                    const char *message) { std::cerr << message << '\n'; });
    if (!validator.Validate(words)) throw std::runtime_error("generated SPIR-V validation failed");
    std::ofstream file(argv[3], std::ios::binary);
    file.write(reinterpret_cast<const char *>(words.data()), words.size() * sizeof(uint32_t));
    if (!file) throw std::runtime_error("SPIR-V output write failed");
    const auto bad = compiler.CompileGlslToSpv("#version 450\nvoid main( {", shaderc_compute_shader,
                                            "invalid.comp", options);
    if (bad.GetCompilationStatus() == shaderc_compilation_status_success || bad.GetErrorMessage().empty())
      throw std::runtime_error("invalid GLSL was accepted or lost its diagnostic");
    auto invalid = words;
    invalid[0] = 0;
    if (validator.Validate(invalid)) throw std::runtime_error("invalid SPIR-V was accepted");
    std::cout << "PASS: " << (argc == 5 ? "port shader regression" : "actual Blender matrix library")
              << " compiled to valid SPIR-V; invalid inputs rejected.\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
