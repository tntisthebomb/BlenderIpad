cmake_minimum_required(VERSION 3.30)
project(BlenderBrowserPlatform LANGUAGES C CXX)
configure_file(probe.html ghost-platform.html COPYONLY)
if(NOT EMSCRIPTEN)
  message(FATAL_ERROR "Configure this target through emcmake")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT BLENDER_SOURCE_DIR)
  message(FATAL_ERROR "BLENDER_SOURCE_DIR must point to the prepared Blender 5.2.2 source")
endif()
set(B "${BLENDER_SOURCE_DIR}")
set(G "${B}/intern/ghost")
set(M "${B}/intern/guardedalloc")
add_library(blender_browser_ghost STATIC
  ${G}/intern/GHOST_Buttons.cc
  ${G}/intern/GHOST_CallbackEventConsumer.cc
  ${G}/intern/GHOST_Context.cc
  ${G}/intern/GHOST_ContextNone.cc
  ${G}/intern/GHOST_EventManager.cc
  ${G}/intern/GHOST_ISystem.cc
  ${G}/intern/GHOST_ModifierKeys.cc
  ${G}/intern/GHOST_Rect.cc
  ${G}/intern/GHOST_System.cc
  ${G}/intern/GHOST_TimerManager.cc
  ${G}/intern/GHOST_Window.cc
  ${G}/intern/GHOST_WindowManager.cc
  ${G}/intern/GHOST_SystemWeb.cc
  ${M}/intern/leak_detector.cc
  ${M}/intern/mallocn.cc
  ${M}/intern/mallocn_guarded_impl.cc
  ${M}/intern/mallocn_lockfree_impl.cc
  ${M}/intern/memory_usage.cc
  ${B}/intern/clog/clog.cc
)
target_include_directories(blender_browser_ghost PUBLIC
  ${G} ${G}/intern ${M} ${B}/intern/atomic ${B}/intern/clog
  ${B}/source/blender/blenlib
)
target_compile_definitions(blender_browser_ghost PUBLIC WITH_GHOST_WEB)
target_compile_options(blender_browser_ghost PRIVATE -O1 -g -fexceptions)
add_executable(ghost-platform-probe ghost_probe.cc)
target_link_libraries(ghost-platform-probe PRIVATE blender_browser_ghost)
target_compile_options(ghost-platform-probe PRIVATE -O1 -g -fexceptions)
target_link_options(ghost-platform-probe PRIVATE
  --no-entry -sMODULARIZE=1 -sEXPORT_NAME=BlenderGhostNative
  -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=33554432 -sMAXIMUM_MEMORY=268435456
  -sASSERTIONS=2 -sDISABLE_EXCEPTION_CATCHING=0
  "-sEXPORTED_FUNCTIONS=['_ghost_probe_init','_ghost_probe_tick','_ghost_probe_snapshot','_ghost_probe_shutdown','_ghost_probe_key_g','_ghost_probe_text','_ghost_probe_redraw','_ghost_probe_close_window','_ghost_probe_reopen_window']"
  "-sEXPORTED_RUNTIME_METHODS=['ccall','UTF8ToString']"
)
