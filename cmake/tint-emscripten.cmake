include("${CMAKE_CURRENT_LIST_DIR}/threaded-emscripten.cmake")
if(EMSCRIPTEN AND CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  # Dawn skips SPIR-V dependencies on Emscripten. Reuse the exact libraries
  # already built for Blender's shaderc rather than mixing two SPIR-V ABIs.
  find_package(SPIRV-Tools CONFIG REQUIRED)
  add_library(SPIRV-Tools ALIAS SPIRV-Tools-static)
  find_package(SPIRV-Tools-opt CONFIG REQUIRED)
  set_property(TARGET SPIRV-Tools-opt APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
    "${DAWN_SPIRV_HEADERS_DIR}/include")
  add_library(SPIRV-Headers INTERFACE)
  target_include_directories(SPIRV-Headers INTERFACE "${DAWN_SPIRV_HEADERS_DIR}/include")
  # Upstream Dawn forces PIC even for static Emscripten targets. Use the
  # same static relocation model as our validated Blender executable.
  function(blender_tint_static_targets directory)
    get_property(targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
    foreach(target IN LISTS targets)
      set_property(TARGET "${target}" PROPERTY POSITION_INDEPENDENT_CODE OFF)
    endforeach()
    get_property(children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
    foreach(child IN LISTS children)
      blender_tint_static_targets("${child}")
    endforeach()
  endfunction()
  cmake_language(DEFER CALL blender_tint_static_targets "${CMAKE_SOURCE_DIR}")
  if(BLENDER_SHADER_PROBE_SOURCE)
    add_executable(blender_shader_translation_probe "${BLENDER_SHADER_PROBE_SOURCE}")
    target_link_libraries(blender_shader_translation_probe PRIVATE tint_api)
  endif()
endif()
