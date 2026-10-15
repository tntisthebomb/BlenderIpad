Startup investigation, 2026-10-14 (America/New_York)

The physical iPad became broadly unresponsive while the old diagnostic was at
Loading engine and restoring projects. No complete device report was recoverable.
The screenshot established secure context and cross-origin isolation, not the
underlying freeze cause. Do not retry that build to collect diagnostics.

A fresh, unmodified stock editor startup also succeeds on the cloud's configured
SwiftShader driver. Earlier device-loss failures came from a different driver
environment and do not establish an application startup lifetime bug.

Measured the actual accepted baseline engine on Chromium/SwiftShader, using a
1180x820 CSS viewport, DPR2, clean caches and a new browser for each case. The
bounded case uses the changed frontend with the same old engine; the new native
pre-js OIIO thread setting is not present in that old binary. Explicit shared
memory uses that baseline's exact 128MiB initial / 1GiB maximum settings solely
for observation. No Python observer or editor fixture was injected. Linux PSS
was sampled every0.5s across Chromium processes, apportioning shared mappings.
These are software-driver measurements, not iPad RAM or Safari benchmarks.

                        Baseline Retina       Bounded tablet
First viewport          31.36s                32.99s
Canvas                  2360x1560             1180x780
Peak browser PSS         1,971,336,192bytes      2,154,027,008bytes
Wasm memory              182,517,760bytes        178,323,456bytes
Backend texture counter  210MB                 189MB

Both cases presented actual native editor pixels and reported no editor errors.
The bounded case does not demonstrate lower peak memory or faster startup. It
reduces a known render-target cost, while engine compilation/initialization
remains expensive. One uncontrolled run per variant cannot isolate a causal RAM
cost; browser PSS includes JIT code, GPU process/driver, Wasm and site workers.

Old baseline WASM is about185MiB:138.73MiB code,19.6MiB data,26.55MiB names.
Startup data archive is about65MiB. Wasm heap size alone badly undercounts browser
resource use. CPU compilation and memory pressure remain plausible contributors;
neither is established as the physical iPad freeze cause.

Changes:
- Standalone ipad-preflight-v2 never loads Blender, creates a GPU device, installs
  an offline worker, or allocates its heap. Browser info immediately selectable;
  optional graphics check only reads the adapter, with10s timeout.
- Copy fallback selects the report; JSON download needs no engine.
- Editor on touch Apple devices waits before engine script, service worker or
  graphics device; one explicit isolation reload carries launch only once.
- iPad canvas capped to CSS resolution,1280x800; Blender/OIIO request1thread.
- Bounded startup phase checkpoint and dependency count, safe native heap-size
  accessor, and stage timeouts. A timeout cannot interrupt synchronous native
  work or force Safari to stop compilation. No claim of a hard memory ceiling.
- Dependency display/storage writes throttled to avoid adding thousands of
  synchronous updates during data-package filesystem initialization.

Validation: engine-free preflight/no requests, no GPU device, explicit launch,
isolation continuation, reload returns to start, selectable clipboard fallback,
download JSON, capped dimensions and thread arguments; file transfer/recovery,
missing installation and service worker offline/coherent-update fixtures pass.
Full fresh native module validation remains in CI; Safari acceptance outstanding.

Renderer/device follow-up

The actual iPad preflight reports compute invocations1024, workgroup storage32KiB,
storage textures44 and storage buffers44 per stage, buffer/binding limits
715827880bytes, and maximum 2D texture dimension16384. depth32float-stencil8
is present; float32-filterable and texture-formats-tier2 are absent. Available
RAM remains unknown. These successful adapter checks do not establish usable
engine startup or explain the freeze.

The next candidate replaces RGBA16F/RGBA32F read/write images with packed buffer
mirrors, synchronized with native textures. RGBA read/write storage requires
texture-formats-tier2; tier1 alone would not fix that incompatibility. Three
Eevee write outputs also use buffers so the captured lighting shader fits four
storage textures and ten storage buffers. Dead resource elimination retains
side effects and resource names. No render output or validation is skipped.

Float32 texel loads and requested nearest sampling now select unfilterable
layouts when optional float32-filterable is absent. Texture format participates
in pipeline cache keys, and internal sampler states are resolved. This does not
implement software linear/anisotropic filtering of float32 textures; requested
linear filtering is not silently changed to nearest.

The iPad low-resource editor now prewarms four pthread workers rather than eight.
A real compiled native thread/join probe verifies four for tablet mode and eight
for desktop mode. The new stock tablet acceptance starts the actual editor with
no injected bpy observer, no float32-filterable feature, explicit launch, real
viewport pixels, exactly four prewarmed workers and a non-starting reload. This
full-module test requires fresh CI and remains separate from physical Safari.

Local verification: native GPU libraries compile; all55 captured real shader
inputs translate and validate, their compute pipelines create, and11 graphics
pairs create pipelines with matching input/output types. Numeric GPU tests check
packed half-floats, float32, arrays/3D, padded rows, out-of-bounds reads and exact
integer outputs. These are shader-level checks; full native engine renders,
new texture/buffer coherence fixtures and stock tablet startup still require
source-matched CI. The iPad freeze and full port acceptance remain unresolved.
