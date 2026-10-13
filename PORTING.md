# Full Blender PWA port: remaining engineering

Target: Blender 5.2.2 LTS, exact commit in `port.lock.json`, on Safari and Home Screen web apps on an iPad 10th generation. Use the existing isolated checkout; do not create a worktree unless explicitly requested.

## What the current build proves

The native browser build now compiles Blender's real GHOST system factory, event queue, window manager, timers, allocator and logging, with a browser implementation adapted for this stable source release. Chromium tests exercise keyboard, UTF-8 text, left/right modifiers, blur release, mouse, touch, wheel, resize, redraw and lifecycle cleanup. The platform currently accepts only `GHOST_kDrawingContextTypeNone`; graphics requests fail explicitly. See [BROWSER_PORT.md](BROWSER_PORT.md) for reproducible commands and the full-application configuration diagnostic.

Selected upstream `blenlib` C++ implementation files compile with WASI SDK 25 and execute inside the browser. The wrapper exposes transformation, matrix inversion, interpolation and normalization. Assertions remain enabled and abort on failure. `MATH_STANDALONE` uses Blender's supported scalar inversion implementation instead of the Eigen C API. The build neither patches upstream source nor links the complete Blender application.

The actual background Blender application now links and executes in Chromium with its static Python interpreter, scripts and startup assets. Tests pass modeling, Solidify, animation, PNG save/load and a native `.blend` round trip after disconnecting the network. The actual editor additionally passes solid viewport, keyboard/touch, native save/load, durable storage and offline application reload checks in Chromium. Render-engine validation and physical iPad acceptance remain outstanding. See BROWSER_PORT.md for the commands and diagnosed extension-manager failure.

## 1. Browser build target and dependencies

The upstream top-level `CMakeLists.txt` loads Unix, Windows or Apple platform configuration. It has no browser platform configuration. Linux library archives cannot be linked into a WASM executable.

Add an explicit Emscripten platform configuration, with separate native builds for code generators and browser builds for runtime code. Audit target sizes and alignment assumptions. Cross-compile required libraries, beginning with allocation, compression, images/fonts, geometry and the Python runtime. Preserve assertions and dependency integrity checks.

Emscripten 4.0.18 is installed and pinned in `browser-port.lock.json`. The native GHOST browser target builds with it. The older math workbench retains its separate checksum-pinned WASI SDK. WASI alone does not supply Blender's browser windowing, GPU or filesystem integration.

`scripts/configure_blender_browser.py` fetches `release/datafiles/startup.blend` through Blender's public upstream LFS endpoint and verifies its SHA256 against the source pointer. It materializes the asset only in `.cache/blender-browser`; the original release checkout remains pristine. The background profile now has its required browser dependencies and code generators. Full graphics/render dependencies remain incomplete; the GHOST probe alone does not establish application behavior.

Acceptance: configure and link a real browser-target Blender binary, with declared dependencies and generated files; verify startup without silently omitting the application or substituting a test executable.

## 2. GHOST windowing and event loop

Upstream `intern/ghost/CMakeLists.txt` selects headless, SDL, Cocoa, X11/Wayland or Windows implementations. Investigate reuse of SDL's browser support, then implement missing GHOST behavior against a browser canvas: sizing, device-pixel ratio, redraw scheduling, cursors, clipboard, keyboard, pointer events and focus.

Replace blocking desktop-loop assumptions with browser-compatible scheduling. Handle visibility changes and suspension. Browser and OS-reserved shortcuts need alternate mappings, not claims of universal interception.

Acceptance: Blender's actual interface starts and responds to a physical keyboard and trackpad on the target iPad. Verify modifiers, key repeats, focus restoration and cancellation in the app itself.

## 3. Graphics backend

`source/blender/gpu/GPU_platform_backend_enum.h` lists OpenGL, Metal and Vulkan. None is a browser WebGPU backend. Browser WebGL is not interchangeable with the desktop OpenGL API used by Blender, and browser JavaScript cannot invoke native Metal directly.

Implement a WebGPU backend for Blender GPU resources, pipelines, command submission, synchronization and shaders. Audit required features against an adapter obtained on the actual A14 device. Shader translation needs to preserve binding layouts, shader semantics and numerical behavior. An available `navigator.gpu` property alone is insufficient: request an adapter and validate the required operations and limits.

Acceptance: the real Blender viewport and Workbench/Eevee draw supported scenes correctly on Safari, with measured memory and frame behavior. The existing Canvas 2D wireframe provides no evidence for these capabilities.

## 4. Python and full editor functionality

Compile and embed a browser-compatible Python interpreter and bundle the standard library and Blender Python modules. Audit C extensions and add-ons individually. Python-driven UI registration is part of Blender startup; disabling Python cannot establish a full editor port.

Acceptance: the real UI initializes; `bpy` manipulates a scene; representative modeling, modifier, animation and scripting workflows execute offline. Keep unsupported add-ons and platform APIs explicit.

## 5. Files and durable offline assets

Adapt file access to a browser filesystem, with persistent project storage where Safari supports it. Provide import through Safari-compatible file inputs and export/download through supported browser APIs; do not depend on desktop filesystem dialogs or assume the File System Access picker API is available. Handle relative paths, textures, linked files and `.blend` saves.

Cache a versioned complete engine, startup data, Python and required assets. Check storage quota, partial-download failures and eviction; expose truthful download/readiness states. Future updates need atomic activation with matching code and assets. Retain source/license access for distributed binaries.

Acceptance: import a `.blend`, change it in Blender, save/export it, close the app, disconnect the network, reopen and restore it. Test texture and linked-asset handling and failure recovery.

## 6. Rendering and iPad resource limits

Port and validate CPU Cycles as a separate target after scene loading, Python and dependencies work. Native CUDA, OptiX, HIP and Metal device backends are not usable directly from a PWA. GPU Cycles would require additional browser compute work; do not promise desktop GPU feature parity.

Four GB of device RAM is shared with iPadOS and is not an application memory allocation. Measure actual Safari memory limits, WASM linear memory, browser/GPU allocations and suspension behavior. Test small scenes before large projects and establish failure/recovery behavior when resources are exhausted.

Acceptance: render a known scene offline on the actual device and compare the result against the same source release. Clearly distinguish supported render engines and devices.

## Completion criteria

Call this a full Blender PWA only after the real editor starts, modeling/scripting/file workflows work, rendering is validated, and a Home Screen installation survives a verified offline relaunch on the target iPad. The background engine passes scene/image/file checks in Chromium. The editor and durable project restoration pass in Chromium. Rendering and physical iPad acceptance criteria remain unmet.
