# Third-party source used in the browser port

`native/browser/GHOST_SystemWeb.cc`, `GHOST_SystemWeb.hh` and `GHOST_WindowWeb.hh` are adapted from [HeyPuter/blender](https://github.com/HeyPuter/blender/tree/6b031d3d41c392883e3c495aa72343e10d15b43d/intern/ghost/intern), commit `6b031d3d41c392883e3c495aa72343e10d15b43d`. Their original Blender Authors copyright notices and GPL-2.0-or-later license identifiers are retained. The project GPL license is in `LICENSE`.

That reference fork identifies itself as Blender 5.3 alpha. We adapted its browser platform files and experimental `source/blender/gpu/webgpu` backend against **stable Blender 5.2.2**. The adapted backend lives in `native/browser/webgpu`. We did not replace the stable core with the alpha fork. Its Tint internal-error recovery and `setjmp` bypass were removed; shader translation errors remain failures.

Our GHOST changes include stable-version factory registration, native touch events, input focus and modifier handling, UTF-8 key text, redraw events, and window/callback cleanup. Its default test profile uses `GHOST_kDrawingContextTypeNone`. The optional WebGPU context owns the canvas surface and enforces frame acquisition, submission and release. The experimental Blender graphics profile connects that context to the GPU backend; baseline editor, viewport, input, project and offline-reload acceptance passes in Chromium; full renderer and physical iPad acceptance remains outstanding.

Backend adaptations include the pinned SDK's Tint API, actual synchronous texture/framebuffer/storage-buffer readback through Asyncify, current-round occlusion query readback, queue fences, pixel staging buffers, and GHOST-owned presentation. These sources retain their upstream GPL identifiers. The reference's diagnostic rendering claims and placeholder paths are not evidence that this port works; application acceptance tests exercise actual Blender GPU resources and pixels.

The application graphics build links Apache-2.0 shaderc/Tint components. Distribution of that combined application uses the GPL-3.0 option permitted by Blender's GPL-2.0-or-later notices, with the original third-party licenses retained. The GPL-3.0 text is in `native/browser/LICENSE-GPL-3.0.txt`; the repository's original `LICENSE` is retained. Complete corresponding source and build instructions must accompany a distributed application artifact.

The exploratory build recipe repository [HeyPuter/blender-wasm](https://github.com/HeyPuter/blender-wasm/tree/f8f811929f8a5bc218e04944cf2dff25eeeccbf3) informed the public upstream LFS endpoint configuration. Its claims of rendering/UI support have not been adopted as our validation results.

That pinned repository also informed the runtime dependency graph and CPython embedding support-object requirements. Our scripts use stable Blender's dependency versions and checksums, preserve original sources, run the documented tests, and do not adopt the reference's undefined-symbol allowance or shader-recovery bypasses.

CPython 3.13.13 retains its PSF license, copied beside the local browser runtime output. The standard-library ZIP contains the installed Python source modules; the interpreter C source is pinned in `browser-port.lock.json`. No runtime probe contains a substitute `bpy` module.

Blender's original GHOST, allocator, logging and dependency code is fetched from the immutable release pin in `port.lock.json`. Dependency archive hashes are taken from that release's `build_files/build_environment/cmake/versions.cmake` and are retained in `browser-port.lock.json`. No checksums or assertions are weakened to accept a build.

Tint atomic composite lowering includes a narrow backport of upstream Dawn fixes. [Patch provenance](patches/tint-atomics-composite.md) records the original commits and retained BSD-3-Clause licensing. The SDK-matched source pin and compiler validation remain in place.

The optional CPU Cycles profile uses oneTBB 2022.3.0, pinned to the archive checksum
in Blender's stable dependency manifest. Its Apache-2.0 license is retained in
the corresponding dependency source. The browser overlay builds the real
scheduler with assertions and pthreads; Node and isolated-browser probes check
parallel work and task completion before the profile can be enabled. These
probes do not establish Cycles rendering support.

CPU Subdivision Surface uses Blender's pinned OpenSubdiv 3.7.0 archive. Its
upstream license is retained in the corresponding dependency source. The build
keeps its topology and stencil regression tests; the application separately
checks a native level-two Catmull–Clark modifier. WebGPU uses CPU evaluation
until the GPU subdivision path has its own acceptance proof.
# Translator corrections

`patches/tint-image-overloads.patch` corrects the pinned Dawn/Tint SPIR-V
`OpImage` overloads for 3D, cube and depth images. Its generated intrinsic table
was regenerated from the corrected `spirv.def` using that same pinned checkout's
`go run ./tools/src/cmd/gen templates src/tint/lang/spirv/intrinsic/data.cc.tmpl`
with Go 1.23.12. Go is only a development generator; the guarded patch includes
the generated table and does not add a Go dependency to the port build.

`patches/tint-image-switch-parser.patch` lowers validated switch fallthrough by
emitting the shared tail in each entry case, with separate nested control-flow
state. Numeric WebGPU regressions check all entry cases, loops, conditional
function calls, nested switches, 3D dimensions and texel fetches. The Dawn
checkout remains pristine and Tint IR validation remains enabled.
