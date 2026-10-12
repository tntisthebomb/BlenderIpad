#!/usr/bin/env python3
"""Probe the full Blender application configuration; preserve failures as failures."""
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

if __name__ == "__main__":
    environment = toolchain()
    source = prepare_source(materialize_assets=True)
    run("emcmake", "cmake", "-S", source, "-B", CACHE / "full-build-browser", "-G", "Ninja",
        "-DWITH_LIBS_PRECOMPILED=OFF", "-DWITH_GHOST_WEB=ON", "-DWITH_GHOST_SDL=OFF",
        "-DWITH_GHOST_X11=OFF", "-DWITH_GHOST_WAYLAND=OFF", "-DWITH_COMPILER_SIMD=OFF",
        "-DWITH_VULKAN_BACKEND=OFF", "-DWITH_BUILDINFO=OFF",
        "-DCMAKE_PREFIX_PATH=" + str(CACHE / "wasm-sysroot"),
        "-DCMAKE_FIND_ROOT_PATH=" + str(CACHE / "wasm-sysroot"), env=environment)
