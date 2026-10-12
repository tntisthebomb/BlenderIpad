#!/usr/bin/env python3
"""Compile the actual Blender GHOST browser backend and its development probe."""
from pathlib import Path
from setup_browser import ROOT, CACHE, toolchain, prepare_source, run

if __name__ == "__main__":
    env = toolchain()
    source = prepare_source()
    build = CACHE / "ghost-build"
    run("emcmake", "cmake", "-S", ROOT / "native/browser", "-B", build, "-G", "Ninja",
        "-DBLENDER_SOURCE_DIR=" + str(source), env=env)
    run("cmake", "--build", build, "--parallel", "4", env=env)
    print("Built real Blender GHOST platform library and WASM probe; graphics/UI are not yet attached.")
