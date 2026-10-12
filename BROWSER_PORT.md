# Native Blender browser port

Target: pinned Blender 5.2.2 LTS on iPad 10th generation, iPadOS 26. This development target compiles actual Blender platform code. It does not display the editor or render a scene yet; the existing `ipad-workbench` download remains the separate math test.

## Build the native platform

Linux x86-64 host, Python 3.12+, Git, `patch`, and HTTPS access are required. Full configuration additionally requires Git LFS. The scripts install pinned Emscripten 4.0.18, CMake 3.31.6 and Ninja 1.11.1.4 into ignored `.cache/` directories. No system toolchain replacement is needed.

```sh
python3 scripts/build_browser_platform.py
python3 tests/ghost_platform_test.py
```

The test requires Python Playwright and Chromium, as documented in README.md. `CHROMIUM_PATH` overrides the existing browser path. It starts and stops its own HTTP server.

Outputs in `.cache/ghost-build/`:

- `libblender_browser_ghost.a`: actual stable GHOST core, browser platform, allocator and logging.
- `ghost-platform-probe.js` and `.wasm`: developer test executable linked against that library.
- `ghost-platform.html`: event inspection harness with a blank canvas. It is deliberately not an editor preview.

The tests verify native system factory selection (`WEB`), window creation, queued events, physical keys, UTF-8 key text, repeats, left/right Shift, blur release, mouse release outside the canvas, touch without duplicated compatibility mouse events, wheel, resize, redraw and repeated shutdown/reinitialization. Assertions remain enabled. These tests passed in Chromium; native Safari behavior has not yet been tested.

`patches/blender-5.2.2-ghost-web.patch` connects the browser implementation to upstream GHOST factory and CMake selection. The preparation script applies it to a separate source copy, verifies the original commit and copied inputs, and refuses unknown edits rather than overwriting them. See THIRD_PARTY.md for the adapted platform files' provenance.

## Cross-compile application dependencies

```sh
python3 scripts/build_browser_deps.py
python3 scripts/configure_blender_browser.py
```

Dependency archive hashes are preserved from this stable Blender release's own manifest. Builds install into `.cache/wasm-sysroot`; host Linux libraries are not substituted for WASM libraries. Dependencies and their upstream validation:

- JPEG: 151 upstream CTest tests passed under Node/WebAssembly.
- zlib: both upstream `example` and `example64` test programs passed.
- PNG: upstream `pngtest` round trip and `pngvalid` pixel/gamma validation passed. The validator's recursive buffer cleanup exceeded the JavaScript engine's call stack; a tracked patch makes only that cleanup iterative. Pixel checks and assertions are preserved. Library sources are unchanged.
- Zstandard: 128 seeded upstream fuzz iterations passed. Its basic unit suite unconditionally requests worker threads and fails against the current single-threaded library; the supported fuzzer starting-test option selects the randomized codec checks instead. Threaded compression remains unverified.

The default dependency build includes these four validated libraries. The optional `python3 scripts/build_browser_deps.py fmt` diagnostic currently fails: 17 of 21 upstream CTest suites pass, while four suites expose unavailable worker threads and missing Spanish/Belarusian locale behavior. C++ exception catching and Emscripten runtime assertions are enabled; test assertions are not removed. The script refuses to install fmt after failed tests. Threading and locale support must be resolved before this prerequisite is ready.

The full configuration command discovers the verified WASM JPEG, PNG, zlib and Zstandard libraries, then currently fails at missing Epoxy. It is a diagnostic and returns failure when prerequisites remain missing; it does not silently substitute the probe executable for Blender.

## Remaining integration

The browser platform currently accepts only `GHOST_kDrawingContextTypeNone` and reports failure for GPU presentation. It is single-window and single-threaded. Clipboard, cursor capture/custom shapes, gestures, IME composition, suspension and device-pixel scaling still need implementation and target-device tests. Browser event pumping in the probe is not a conversion of Blender's full application main loop.

The full application's dependency discovery still uses upstream Unix platform configuration. Its required Epoxy library is for native OpenGL dispatch, not WebGPU. A browser platform configuration and a real GPU backend must replace that route; installing native Epoxy or returning success from empty presentation methods would not solve it.

Python/UI registration, scene/file operations, host code generation, offline asset packaging and rendering remain incomplete. PORTING.md lists acceptance checks for each. No full Blender WASM binary or working full editor is distributed by this milestone.

Safari WebGPU on iPadOS 26 requires a secure context. An ordinary HTTP `users-ipad.local` address from WorldWideWeb can serve the math/native event tests, but cannot establish a working WebGPU PWA. A browser-recognized loopback origin or HTTPS must be verified for graphics development. No permanent hosting service is required for computation; the engine is intended to execute locally.
