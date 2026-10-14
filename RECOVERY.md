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

Real offline Workbench PNG rendering and modeling/geometry-node/rigging/OBJ
round trips passed on the baseline engine. Updated storage, failed-install and
atomic-update fixtures also passed. The new full binary still needs acceptance;
Eevee and CPU Cycles rendering in the complete editor remain unproven. The real
isolated Cycles CPU engine produced correct red and green PNGs offline, which
does not establish the full editor's rendering or iPad memory suitability.
OpenSubdiv's five upstream CPU tests and Blender's evaluator library compile
passed; the application fixture must still prove the Subdivision Surface modifier.

The local 8 GiB builder could compile the editor but exceeded memory at the
full-module Asyncify link. Public-runner builds at source `f0c26df` linked both
profiles, then failed native Python startup with a stack overflow. The staged
optimizer had lost Asyncify's optimization level; its second process now retains
that level so Asyncify can coalesce locals. Validate both real CPython suspension
and the complete application before accepting this correction. CI preserves
incremental objects for follow-up builds. Preserve O2, assertions and Asyncify.
The real oneTBB Node/browser scheduler probes and CPU Cycles kernel/device/
utility compilation also pass; actual integrated rendering remains a gate.

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
- `.cache/blender-webgpu-browser/`: extracted accepted runtime and CI acceptance proof.
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

1. Validate real offline scene rendering and output images. Workbench/Eevee
   rendering is not established by viewport acceptance. Cycles is disabled.
2. Verify Safari and Home Screen operation on the target iPad 10th generation,
   iPadOS 26, including adapter features, actual memory limits and usable input.
3. Exercise suspension/resumption, graphics device loss, storage eviction/quota,
   interrupted installation and coherent application updates.
4. Audit disabled optional features, extensions, textures/linked projects,
   clipboard/IME and browser-specific input limitations against the full goal.
5. Establish a usable HTTPS installation path with the necessary isolation
   headers. The Pages workflow and older WorldWideWeb ZIPs are the math demo.

Keep Blender's source and dependency pins unchanged unless intentionally
updating the release. Render validation is the next independent engineering
step; physical-device acceptance requires an actual iPad and cannot be inferred
from the cloud browser.
