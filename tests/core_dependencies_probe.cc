/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <OpenImageIO/imageio.h>
#include <OpenColorIO/OpenColorIO.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <array>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool condition, const char *message)
{
  if (!condition) throw std::runtime_error(message);
}
int main(int argc, char **argv)
{
  try {
    require(argc == 3, "expected asset and output directories");
    const std::filesystem::path assets(argv[1]), output(argv[2]);
    std::filesystem::create_directories(output);
    OIIO::attribute("threads", 2);
    OIIO::attribute("exr_threads", 2);
    for (const char *extension : {"png", "tif", "exr"}) {
      const std::string filename = (output / (std::string("roundtrip.") + extension)).string();
      OIIO::ImageSpec spec(8, 8, 4, OIIO::TypeDesc::UINT8);
      std::vector<unsigned char> pixels(8 * 8 * 4);
      for (int i = 0; i < 64; ++i) {
        pixels[4*i] = static_cast<unsigned char>(i*3);
        pixels[4*i+1] = static_cast<unsigned char>(255-i*3);
        pixels[4*i+2] = 64;
        pixels[4*i+3] = 255;
      }
      auto writer = OIIO::ImageOutput::create(filename);
      require(bool(writer), "image writer unavailable");
      require(writer->open(filename, spec), "cannot open image output");
      require(writer->write_image(OIIO::TypeDesc::UINT8, pixels.data()), "image write failed");
      require(writer->close(), "image output close failed");
      auto reader = OIIO::ImageInput::open(filename);
      require(bool(reader), "image reader unavailable");
      std::vector<unsigned char> decoded(pixels.size());
      require(reader->read_image(0, 0, 0, 4, OIIO::TypeDesc::UINT8, decoded.data()), "image read failed");
      require(reader->close(), "image input close failed");
      for (size_t i = 0; i < pixels.size(); ++i) {
        require(std::abs(int(decoded[i])-int(pixels[i])) <= 1, "image roundtrip pixels differ");
      }
    }
    namespace OCIO = OCIO_NAMESPACE;
    const auto config = OCIO::Config::CreateFromFile((assets / "colormanagement/config.ocio").c_str());
    const auto processor = config->getProcessor(OCIO::ROLE_SCENE_LINEAR, OCIO::ROLE_COLOR_PICKING)->getDefaultCPUProcessor();
    float rgb[] = {0.18f, 0.18f, 0.18f};
    processor->applyRGB(rgb);
    const double expected = 1.055 * std::pow(0.18, 1.0 / 2.4) - 0.055;
    for (float value : rgb) require(std::abs(value-expected) < 0.001, "scene-linear to sRGB transform differs");
    FT_Library library;
    FT_Face face;
    require(FT_Init_FreeType(&library) == 0, "FreeType startup failed");
    require(FT_New_Face(library, (assets / "fonts/Inter.woff2").c_str(), 0, &face) == 0, "Blender's actual WOFF2 font did not load");
    require(FT_Set_Pixel_Sizes(face, 0, 24) == 0, "font size failed");
    require(FT_Load_Char(face, 'A', FT_LOAD_RENDER) == 0, "glyph rendering failed");
    require(face->glyph->bitmap.width > 0 && face->glyph->bitmap.rows > 0, "glyph has no pixels");
    bool coverage = false;
    for (unsigned row = 0; row < face->glyph->bitmap.rows; ++row)
      for (unsigned col = 0; col < face->glyph->bitmap.width; ++col)
        coverage |= face->glyph->bitmap.buffer[row*face->glyph->bitmap.pitch+col] != 0;
    require(coverage, "glyph bitmap is blank");
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    puts("PASS: real WASM PNG/TIFF/EXR pixel roundtrips, Blender colour configuration, sRGB transform and WOFF2 glyph rasterization.");
    return 0;
  } catch (const std::exception &error) {
    fprintf(stderr, "FAIL: %s\n", error.what());
    return 1;
  }
}
