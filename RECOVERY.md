# Resume baseline

Recovered October 13, 2026 (America/New_York). Start here when resuming this project.

## Active work after recovery

The user authorized finishing the port and will test on an iPad 10th generation
with iPadOS 26, served by WorldWideWeb. Use `IPAD_ACCEPTANCE.md` for that path.
The latest engineering candidate is the head of `codex/ipad-port-completion`,
preserved in [draft PR #1](https://github.com/tntisthebomb/BlenderIpad/pull/1).
Use its latest editor workflow result, checking the run's source SHA against the
branch head. The first candidate run is
[38521444931](https://github.com/tntisthebomb/BlenderIpad/actions/runs/38521444931).
The candidate is not an accepted distribution. The baseline below remains the
latest verified downloadable editor until the new engine gates pass.
`work/SESSION_STATE.md` records active processes, local follow-up changes and
diagnostic results for a resumed local session.

The baseline distribution in `dist/` remains intact. The current
`.cache/blender-webgpu-browser/` is a diagnostic runtime with updated frontend
files, not an accepted distribution; its old proof was moved to
`work/recovery/editor-validation-original.json`. Rebuild the native application,
run CLI acceptance, relink the browser application and validate its exact assets
before packaging. Do not distribute that diagnostic cache.

The full-source candidate `2c90fac911f1ec4ee4eb9d394cb9ff229ad46422`,
[run 38629226031](https://github.com/tntisthebomb/BlenderIpad/actions/runs/38629226031),
linked both profiles and passed actual native CLI validation. Browser tests
passed GPU resources, offline Workbench rendering, modeling/geometry nodes,
rigging, CPU Subdivision Surface, embedded Python threads, storage/install/update
handling and the complete editor lifecycle, including actual scheduler pause
and device-loss backup. The CPU profile also passed real native Cycles PNG
rendering. Both profiles failed Eevee; this candidate is not a distribution.

Current follow-ups replace the unsafe Tint switch-parser patch with GLSL
fallthrough lowering before SSA construction, preserve binding names while
removing colliding local debug names, enable the WGSL read/write storage
language feature, implement coherent atomic images using real buffer atomics,
and adapt Eevee workgroups, z bins, hierarchical depth and mip copies to portable
hardware limits. Shadow pool allocation respects the atomic backing capacity.
The actual failing light-culling shader now translates. Numeric WebGPU tests
pass switches, nested control flow, scoped names, 3D dimensions/texels,
read/write storage and 1,024 contending atomic-image invocations. These isolated
results do not establish a complete Eevee render. Both source profiles must
pass all gates again before packaging.

Extended full-engine Cycles diagnostics passed world diffuse and rough-metal
red/green lighting, with direct lights disabled. The updated renderer fixture
requires those world-probe paths from Eevee too. Preserve assertions, O2,
Asyncify and the real Emscripten runtime keepalive around scheduler suspension.
Never package the manually corrected diagnostic runtime in the local cache.

The next follow-up also corrects the three remaining a19580bf shader failures:
interface fields with identical names flattening into one WGSL output struct,
a multidimensional shared array unsupported by Blender's BSL preprocessor,
and G-buffer macro redefinition. A focused vertex/fragment test reproduced the
name failure and now renders the expected pixel after member disambiguation.
Native on-screen keyboard tests pass ASCII, Ctrl+A, Unicode composition, arrow
movement and backspace; the control is included in offline cache validation.
Shader destruction also clears pipeline caches: pointer reuse had selected an
older shader's storage format during actual GPU diagnosis. Full source-matched
acceptance must validate these changes before distribution.

The tablet-input follow-up adds two-finger drag and pinch through real native
GHOST trackpad events, releases the first finger's selection press when a
gesture starts, and suppresses a new selection drag until all fingers lift.
The compiled native platform probe passes pan/zoom deltas, cancellation,
selection release and a subsequent tap. The full editor fixture additionally
requires actual viewport rotation/zoom with unchanged Cube coordinates; that
new full-module check has not passed yet. A residual barrier was removed from
the serial shadow-amend scan; the focused translator accepts both variants, so
this cleanup is not evidence that the remaining Eevee gate passes.
README.md now links the verified baseline download and explains extracting and
serving it through WorldWideWeb. Its newer keyboard/gesture controls are not in
that old preview.

Candidate `daad706f751469f64888a86a6002ae5704ccd604` (run 38647318419)
passed GPU resources, the shader lifetime/cache regression, Workbench, modeling,
native keyboard/Unicode, persistence and recovery; both profiles still failed
Eevee. Its captured inputs exposed residual Tint output-symbol reuse and
unsupported normalized image formats. The follow-up patches Tint's output
flattening directly and maps normalized storage to quantized float32 backing.
All 44 captured native shaders now compile/translate and pass actual WebGPU
shader-module validation; their compute pipelines also create successfully.
Numeric GPU tests pass normalized RG16 and RGB10_A2 clamping/quantization.
These shader checks still require the full source-matched rendering test.
The startup screen now provides explicit same-port/path loopback links for
insecure local-server addresses and keeps Device report accessible while loading.
The real-browser insecure-origin recovery test passes.

## Authoritative state

- Repository: https://github.com/tntisthebomb/BlenderIpad
- Current source baseline: `9564a94d44b66dd0929d4e70b40285f332cc3b49`.
- Successful full editor workflow: https://github.com/tntisthebomb/BlenderIpad/actions/runs/38463349693
- Editor plus corresponding source artifact: `blender-editor-preview-with-source`, ID `11852511697`.
- CI diagnostics artifact: `blender-editor-diagnostics`, ID `11852788010`.
- No GitHub release exists at recovery time. Actions artifacts are the latest verified distribution.

The workflow passed native application validation, browser GPU/editor acceptance,
and packaging on a clean runner. `README.md` and the opening of `BROWSER_PORT.md`
describe this current milestone. Intermediate entries further down that log
record earlier failures and are not the current status.

## Restored local files

The tracked source was current, but the restored ignored build cache was from
October 12 and lacked the accepted editor. Do not treat cached application
objects, prepared source or old top-level download ZIPs as current editor outputs.
The restored `origin/main` tracking ref was also stale; the local `work` branch
and GitHub's actual `main` both identified the baseline above.

Recovered outputs:

- `dist/BlenderIpad-5.2.2-editor-preview.zip`
- `dist/BlenderIpad-5.2.2-editor-preview-source.tar.gz`
- `.cache/blender-webgpu-browser/`: currently an unaccepted diagnostic runtime; original proof is preserved separately.
- `work/recovery/ci-diagnostics/`: original CI screenshot and logs.
- `work/recovery/artifact-verification.json`: recovery verification record.

The downloaded outer ZIPs match GitHub's SHA256 digests. Every runtime asset and
all four acceptance fixtures match `editor-validation.json`. The `core.html`
developer harness was copied from the matching source to permit local GPU tests;
it is not an additional packaged application asset. The CI proof is preserved.

Run the same acceptance checks against the restored application:

```sh
cd /workspace/BlenderIpad
.cache/browser-tests/bin/python tests/blender_gpu_browser_test.py
.cache/browser-tests/bin/python tests/blender_editor_browser_test.py
```

These tests use Chromium, not Safari. Recovery test logs are under
`work/recovery/`. Rebuilding requires refreshing the prepared source and
dependencies through the pinned scripts in README.md. Do not package from the
old caches merely because the recovered runtime has a valid acceptance proof.

Both GPU and full editor acceptance passed again in the restored environment.
The editor rerun includes real keyboard/touch events, native project save/load,
durable file bytes and a new application runtime with the network disconnected.

## Proven scope and next work

Blender 5.2.2, actual embedded Python, native editor UI, solid viewport, GPU
resource/font pixels, keyboard transforms, touch selection, native save/load,
durable project storage and offline application reload passed Chromium CI.
Background modeling, modifiers, animation and image operations also passed.

Remaining full-port gates:

1. Complete actual offline Eevee rendering, including world lighting and shadows,
   and rerun all checks against freshly linked source-matched profiles.
2. Verify Safari and Home Screen operation on the target iPad 10th generation,
   iPadOS 26, including actual memory limits, rendering and usable input.
3. Repeat suspension, rotation, device loss and file recovery on that iPad.
4. Audit disabled optional features, extensions, linked projects, clipboard/IME
   and browser-specific input limitations against the full goal.
5. Validate the actual editor through WorldWideWeb at a trusted localhost URL,
   including isolation, installation and disconnected launch. Older Pages and
   WorldWideWeb ZIPs may contain the earlier math demo; verify build identity.

Keep Blender's source and dependency pins unchanged unless intentionally
updating the release. Physical-device acceptance requires the actual iPad and
cannot be inferred from the cloud browser.
