# zlib 1.3.1 explicitly declares shared and static targets named libz. Emscripten
# converts the shared target to static, which makes Ninja see duplicate outputs.
# Give the compatibility target its own output name; retain libz.a for Blender.
if(EMSCRIPTEN)
  function(blender_port_name_zlib_compat_target)
    if(TARGET zlib AND TARGET zlibstatic)
      set_target_properties(zlib PROPERTIES OUTPUT_NAME z-browser-compat)
    endif()
  endfunction()
  cmake_language(DEFER CALL blender_port_name_zlib_compat_target)
endif()
