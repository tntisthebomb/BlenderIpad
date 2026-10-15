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
