# Keep oneTBB's static browser build on Blender's validated relocation model.
# Native stack-clash instrumentation is unavailable in WebAssembly; the WASM
# runtime enforces its stack allocation. Keep all warnings and library asserts.
include("${CMAKE_CURRENT_LIST_DIR}/threaded-emscripten.cmake")
if(EMSCRIPTEN AND CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  function(blender_tbb_browser_options)
    get_target_property(options tbb COMPILE_OPTIONS)
    list(REMOVE_ITEM options "-fPIC" "-fstack-clash-protection"
         "-D__TBB_EMSCRIPTEN_STACK_SIZE=65536")
    set_property(TARGET tbb PROPERTY COMPILE_OPTIONS "${options}")
    target_compile_definitions(tbb PUBLIC TBB_USE_ASSERT=1)
    target_compile_definitions(tbb PRIVATE __TBB_EMSCRIPTEN_STACK_SIZE=2097152)
    set_property(TARGET tbb PROPERTY POSITION_INDEPENDENT_CODE OFF)
  endfunction()
  cmake_language(DEFER CALL blender_tbb_browser_options)
endif()
