# Native Blender browser port

Target: pinned Blender 5.2.2 LTS on iPad 10th generation, iPadOS 26. The real background Blender application and `bpy` run in Chromium with packaged local assets. Modeling, Solidify, animation, PNG save/load, original startup loading and a native `.blend` round trip pass after network disconnect. The editor and renderer are not available yet; the existing `ipad-workbench` download remains the separate math test. Safari and the physical iPad remain untested.

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
python3 scripts/test_blender_core.py
# After the real CLI scene test passes:
python3 scripts/build_browser_python_probe.py
python3 scripts/build_blender_core_browser.py
.cache/browser-tests/bin/python tests/blender_core_browser_test.py
```

The separate `.cache/wasm-threaded-sysroot` prevents mixing this runtime's ABI with the older single-threaded workbench. The application profile explicitly starts with background Blender and Python, without graphics or Cycles. It retains Blender assertions and rejects undefined link symbols. `cmake/browser-core.cmake` lists the disabled development features; this profile is not advertised as the full editor.

The preparation script fetches and SHA256-verifies all 197 LFS assets under `release/datafiles/`, including startup data, fonts and colour resources, in the separate browser source copy. The original Blender checkout remains pristine. DNA/RNA and data generators run through the pinned Node emulator. The shader text preprocessor builds from the same stable source as a native host tool. A scope-constructor fix assigns the invalid-index sentinel to the actual member rather than a local parameter; 24 WASM shader and shader-info outputs match the native tool byte for byte. It generates shader text/metadata, not target memory layouts. The core patch makes native OpenGL dispatch conditional on an enabled OpenGL backend.

The static application explicitly omits Unix Python's `export-dynamic` flag. Exporting every function exceeded V8's 100,000-export limit and inflated the launcher to 89 MB. Unix PIC flags are also removed for this static executable. Its original PIC build produced an invalid direct call in mesh selection, with a global-index relocation where a function index was required. Browser builds must pass validation and actual application startup; a linker output file alone is insufficient evidence.

The acceptance scripts exercise the real `bpy`: load the release's original startup file, create a plane, evaluate Solidify, interpolate animation, save and reload PNG pixels, save a native `.blend` and reopen it with Unicode object names intact. The browser relinker requires successful CLI validation tied to the exact binary hashes. Its developer harness packages the real scripts, startup assets and zipped Python library into Emscripten's virtual filesystem. It uses the headless application; there is no substitute scene implementation, visible editor, renderer, persistent project storage or offline-relaunch claim.

WebAssembly does not expose CPU floating-point exception flags. The expression patch implements explicit per-evaluation error tracking, including errors masked by later clamping, without shared mutable state or folding invalid constants. Thirty-five actual parser/evaluator cases passed, including upstream divide-by-zero/domain examples, error precedence, short-circuiting and the native evaluator's accepted overflow behavior. Run `python3 scripts/test_driver_expressions.py` after building the GHOST allocator library. The resource-scope size assertion is expressed as two pointer widths, preserving its layout check on wasm32 and native 64-bit builds.

Required compression/image/font/colour libraries are cross-compiled from the stable release's checksum pins. Brotli's 14 upstream tests and Imath's 38 registered test commands passed. Threaded JPEG's 155 tests, PNG validation and Zstandard's basic unit suite plus 128 fuzz iterations passed. The combined dependency probe also passes real PNG/TIFF/EXR pixel and string-metadata round trips, Blender's actual scene-linear-to-sRGB colour configuration, and WOFF2 glyph rasterization. Run `python3 scripts/test_core_dependencies.py`. This validates those library operations; full application workflows remain separate acceptance checks.

The wasm32 DNA patch computes native alignment separately from the existing desktop layout models. It emits explicit padding members into the serialized native schema and retains compiler verification of every original member offset and struct size. Runtime `.blend` reconstruction continues using the file's own schema; it does not guess scalar alignment from pointer width, which would misread older 32-bit desktop files. The generated `dna_verify.cc` compiles successfully. Original release startup loading and native 32-bit `.blend` round trips now pass in the actual application, both under Node and in Chromium.

The threaded fmt core profile passes 21 upstream test suites, including its formerly failing thread test. It explicitly excludes four unavailable non-C-locale date tests using `tests/fmt_classic_locale_env.js`. This exclusion is not a localization fix; the complete diagnostic described below still exposes the unsupported locale behavior.

OpenImageIO's narrow compatibility patch adds Emscripten's POSIX declarations and C-locale comparisons. Its memory metrics refer to allocated linear memory and the configured engine heap ceiling, not physical iPad RAM or total browser/GPU memory. The original dependency sources are retained; three patched translation units are staged separately and selected through CMake.

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

The default browser platform accepts `GHOST_kDrawingContextTypeNone` and reports failure for GPU presentation. A separate opt-in WebGPU context now attaches a real canvas surface; see the validated context profile below. It is single-window and single-threaded. Clipboard, cursor capture/custom shapes, gestures, IME composition, suspension and device-pixel scaling still need implementation and target-device tests. Browser event pumping in the probe is not a conversion of Blender's full application main loop.

The full application's dependency discovery still uses upstream Unix platform configuration. Its required Epoxy library is for native OpenGL dispatch, not WebGPU. A browser platform configuration and a real GPU backend must replace that route; installing native Epoxy or returning success from empty presentation methods would not solve it.

Python scene/image/file operations and host code generation pass the background-engine checks. Full UI registration, graphics, durable storage, offline PWA relaunch and rendering remain incomplete. PORTING.md lists acceptance checks for each. No full Blender WASM binary or working full editor is distributed by this milestone.

Safari WebGPU on iPadOS 26 requires a secure context. An ordinary HTTP `users-ipad.local` address from WorldWideWeb can serve the math/native event tests, but cannot establish a working WebGPU PWA. A browser-recognized loopback origin or HTTPS must be verified for graphics development. No permanent hosting service is required for computation; the engine is intended to execute locally.

## Verified background application and remaining failures

Both acceptance scripts pass with the actual application, not a substitute library or scene model. The browser test loads packaged assets, disconnects the network, then executes modeling, modifier evaluation, animation, PNG save/load and native `.blend` save/reload. This verifies execution after loading; it does not verify cached app relaunch, persistence across closing the browser, or target-device performance.

Blender uses `BLENDER_SYSTEM_RESOURCES` for its bundled scripts and `BLENDER_SYSTEM_PYTHON` for the interpreter home; its default isolated interpreter ignores generic Python environment paths. The CLI forwards only explicit non-secret path selectors and writes thumbnails under an owned `XDG_CACHE_HOME`. Browser paths refer only to the packaged virtual filesystem.

OpenImageIO attempted to rewrite libc++ string internals using a legacy layout. Emscripten uses libc++ ABI v2, so long metadata names became invalid PNG keywords. The port uses the existing ordinary string-copy fallback. The expanded dependency probe preserves Software metadata through PNG/TIFF/EXR, and the actual Blender image save/load test passes.

The default extension manager still reports a registration failure because its remote asset downloader requires native Python multiprocessing. External subprocesses and their extension-installation workflows are not ported. This does not prevent the tested background scene operations, but it prevents a claim of complete startup/extension support. Emscripten also reports unsupported `prlimit64`; OS resource-limit APIs are not established.

## Verified WebGPU shader translation prerequisites

```sh
python3 scripts/build_browser_shaderc.py
python3 scripts/test_browser_shaderc.py
python3 scripts/build_browser_tint.py
python3 scripts/test_browser_tint.py
.cache/browser-tests/bin/python tests/shader_webgpu_test.py
python3 scripts/build_browser_webgpu_probe.py
.cache/browser-tests/bin/python tests/webgpu_native_browser_test.py
```

Shaderc 2025.4, glslang, SPIR-V Headers and SPIR-V Tools 2026.1 use the exact stable Blender manifest pins and verified source archives. The probe runs Blender's real shader text preprocessor on its matrix library, compiles a compute shader that calls that library on a runtime-supplied matrix, and validates the SPIR-V. Malformed GLSL and corrupted SPIR-V must be rejected. It does not require compiling the full background application.

Tint uses Dawn commit `01940842b667a7812d0e4ca0ef4367fbec294241`, matching the Emdawnwebgpu package pinned by Emscripten 4.0.18. Abseil uses that Dawn release's DEPS commit. Both checkouts must remain clean. The translator reuses the same SPIR-V libraries as shaderc, including the original internal headers and generated tables. It retains IR validation and normal failure propagation. No internal-compiler-error recovery or shader-skipping workaround is imported from the reference fork. Dawn's forced PIC is disabled through CMake target properties for the validated static WASM relocation model.

The translation probe must read the actual SPIR-V, produce WGSL, parse that WGSL successfully and reject invalid inputs. The browser probes must execute the emitted WGSL and read back the correct inverse of a non-diagonal matrix and Blender's zero/false result for a singular matrix. The native probe additionally exercises the actual C API for adapter/device acquisition, pipeline creation, storage buffers, queue submission and asynchronous mapping.

These are renderer prerequisites, separate from Blender's GPU backend. The tests request a Chromium software WebGPU adapter in the cloud; they do not establish A14/Safari compatibility, graphics performance, the complete shader corpus, editor presentation or offline PWA relaunch. The native probe currently runs on the main browser thread; device/context handling for Blender's application thread remains to be integrated. Use the manually dispatched `Validate Blender browser shader translation` workflow for a clean-runner check.

Local acceptance passed for GLSL → validated SPIR-V → WGSL → WebGPU dispatch/readback, and for the native WASM WebGPU API probe. Both normal and singular runtime matrix cases pass. The complete renderer remains unimplemented.

## GHOST WebGPU canvas context

```sh
python3 scripts/build_browser_ghost_webgpu.py
.cache/browser-tests/bin/python tests/ghost_webgpu_browser_test.py
```

This separate `.cache/ghost-webgpu-build` profile enables `WITH_GHOST_WEBGPU_CONTEXT`. The real GHOST factory rejects a GPU window before device bootstrap, then registers a WebGPU window with an actual configured canvas surface. The context owns device/surface/frame references, obtains the browser's preferred canvas format, updates the surface size, and exposes its acquired texture/view to a future GPU backend. It requires command submission before frame release and rejects duplicate acquire/release operations. Browsers present when the animation frame yields; calling the native `wgpuSurfacePresent` would abort, so that unsupported API is not used.

Acceptance passes real GPU render-pass clears, canvas-texture pixel readback and visible canvas screenshot pixels, continuous animation frames, surface resize, window close/recreation and full native shutdown. The screenshot assertion requires the rendered colour; a blank image fails. The separate default GHOST event profile remains available without WebGPU. This currently requires the main browser thread; application-worker integration and device-loss recovery remain unimplemented. No Blender GPU backend, scene drawing or editor UI is attached.

Cloud canvas validation selects Chromium's bundled SwiftShader Vulkan ICD when present. Without it, this cloud browser accepted compute work but failed canvas shared-image allocation. Adding `--disable-vulkan-surface` allowed readback but yielded a blank screenshot; removing that flag restored visible output. The test preserves native errors and validates actual screenshot pixels with Pillow 12.0.0. These are cloud test settings, not iPad setup requirements. The application still needs an animation-frame presentation loop and idle-frame preservation; a sequence of GPU reads alone does not prove visible output.

The previous clean background-engine workflow reached the final link but exceeded its 90-minute limit. Its limit is now 180 minutes. The independently dispatched shader-translation workflow passed on a clean GitHub runner; background application validation has passed locally but the complete fresh-runner application checks are not yet confirmed.
