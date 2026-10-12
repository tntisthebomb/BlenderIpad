# Native Blender browser port

Target: pinned Blender 5.2.2 LTS on iPad 10th generation, iPadOS 26. Native GHOST and the matching Python runtime are tested in Chromium. The real Blender application is now being integrated, but the editor and renderer are not available yet; the existing `ipad-workbench` download remains the separate math test.

## Actual Python runtime

```sh
python3 scripts/build_browser_deps.py --threaded zlib
python3 scripts/build_browser_python.py
python3 scripts/build_browser_python_probe.py
python3 tests/python_runtime_test.py
```

This builds Blender's pinned CPython 3.13.13, including a matching native host interpreter for code generation. Its source checksum comes from the stable Blender manifest. The browser probe links its actual static C API and uses a deterministic compressed standard-library ZIP (about 2.6 MB). It requires COOP/COEP isolation headers for the shared-memory runtime; the test server supplies them.

Chromium validation covers UTF-8/JSON, arithmetic, decimal, compression, hashing, XML, an actual Python thread, memory-filesystem I/O, failure propagation and another operation after network disconnect. The interpreter and its native standard-library modules execute as WASM. This is not `bpy`, a substitute Blender implementation, durable project storage, or an offline reload test. Only the dependency runtime is established at this stage.

## Full application integration

```sh
python3 scripts/build_browser_core_deps.py
python3 scripts/build_blender_core.py
```

The separate `.cache/wasm-threaded-sysroot` prevents mixing this runtime's ABI with the older single-threaded workbench. The application profile explicitly starts with background Blender and Python, without graphics or Cycles. It retains Blender assertions and rejects undefined link symbols. `cmake/browser-core.cmake` lists the disabled development features; this profile is not advertised as the full editor.

The preparation script now fetches and SHA256-verifies all 197 LFS assets under `release/datafiles/`, including startup data, fonts and colour resources, in the separate browser source copy. The original Blender checkout remains pristine. DNA/RNA and data generators run through the pinned Node emulator. The shader text preprocessor builds from the same stable source as a native host tool: its WASM lexer rejects valid resource-table attributes. It generates shader text/metadata, not target memory layouts. The core patch makes native OpenGL dispatch conditional on an enabled OpenGL backend.

WebAssembly does not expose CPU floating-point exception flags. The expression patch implements explicit per-evaluation error tracking, including errors masked by later clamping, without shared mutable state or folding invalid constants. Thirty-five actual parser/evaluator cases passed, including upstream divide-by-zero/domain examples, error precedence, short-circuiting and the native evaluator's accepted overflow behavior. Run `python3 scripts/test_driver_expressions.py` after building the GHOST allocator library. The resource-scope size assertion is expressed as two pointer widths, preserving its layout check on wasm32 and native 64-bit builds.

Required compression/image/font/colour libraries are cross-compiled from the stable release's checksum pins. Brotli's 14 upstream tests and Imath's 38 registered test commands passed. Threaded JPEG's 155 tests, PNG validation and Zstandard's basic unit suite plus 128 fuzz iterations passed. The combined dependency probe also passes real PNG/TIFF/EXR pixel round trips, Blender's actual scene-linear-to-sRGB colour configuration, and WOFF2 glyph rasterization. Run `python3 scripts/test_core_dependencies.py`. This validates those library operations; full application workflows remain separate acceptance checks.

The wasm32 DNA patch computes native alignment separately from the existing desktop layout models. It emits explicit padding members into the serialized native schema and retains compiler verification of every original member offset and struct size. Runtime `.blend` reconstruction continues using the file's own schema; it does not guess scalar alignment from pointer width, which would misread older 32-bit desktop files. The generated `dna_verify.cc` compiles successfully. Actual old/new `.blend` round trips remain pending until the application starts.

The threaded fmt core profile passes 21 upstream test suites, including its formerly failing thread test. It explicitly excludes four unavailable non-C-locale date tests using `tests/fmt_classic_locale_env.js`. This exclusion is not a localization fix; the complete diagnostic described below still exposes the unsupported locale behavior.

OpenImageIO's narrow compatibility patch adds Emscripten's POSIX declarations and C-locale comparisons. Its memory metrics refer to allocated linear memory and the configured engine heap ceiling, not physical iPad RAM or total browser/GPU memory. The original dependency sources are retained; two patched translation units are staged separately and selected through CMake.

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
