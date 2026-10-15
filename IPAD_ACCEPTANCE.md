# WorldWideWeb and physical iPad acceptance

Target: iPad 10th generation, iPadOS 26. The cloud's Chromium results are separate
from acceptance on this device. Use the experimental **editor** ZIP, not the old
`ipad-workbench` math demo. See RECOVERY.md for the source baseline and artifacts.

## Startup investigation — do not retry the affected preview

The physical iPad became unresponsive while the old preview was loading its
engine. Its diagnostic could not be copied. The cause has not been established;
there is no successful Safari startup acceptance yet. Do not keep retrying that
build or clear saved website data to diagnose it.

`ipad-startup.html` is now an engine-free preflight page. It reports browser
information immediately; **Check graphics support** only requests an adapter,
without creating a GPU device, allocating Blender memory or installing the
service worker. Its selectable report and download work before any engine load.
Available RAM is unknown on Safari and is not inferred from WebGPU limits.

The updated editor waits for **Start Blender** on touch-capable Apple devices,
including iPad desktop mode. Reloading a stalled/killed editor returns to that
choice. A one-time isolation reload after an explicit start preserves the choice
only for that reload. The iPad viewport is capped at CSS resolution and
1280×800 pixels; Blender and OIIO request one thread, with four prewarmed pthread workers instead
of the desktop pool of eight. These changes reduce known
costs; they do not establish that the full editor is usable on the target iPad.
Timeouts cannot interrupt synchronous Wasm compilation or native main-thread work.
Close the tab if the device becomes sluggish; don't try to collect a live report.

## Install

1. Extract the editor ZIP in Files. In WorldWideWeb, select the folder containing
   `index.html`, `blender-core.wasm`, `blender-core.data` and `service-worker.js`.
2. Keep WorldWideWeb running, preferably alongside Safari while downloading.
   Copy its supplied address into Safari, preserving its port and path but
   replacing the hostname with `localhost`. For example, use
   `http://localhost:8080/` in place of `http://users-ipad.local:8080/`.
   If the localhost connection fails, try `127.0.0.1` with the same port/path.
   An ordinary HTTP `.local` or Wi-Fi IP address will not enable this editor.
3. On an updated, device-tested build, choose **Start Blender**. Wait for Blender's actual interface and the offline-ready message. Initial
   shader compilation can be slow. A loading overlay or an error is not readiness.
4. Choose Share → Add to Home Screen. Open that new app while WorldWideWeb is
   still serving, and wait for its interface/offline-ready state too. Safari's
   successful install alone does not prove the installed app has its own cache.

Keep using the same hostname, port and path. Storage and the offline installation
belong to that origin. This localhost route still needs verification on the real
iPad; the Device report records actual security, isolation and adapter behavior.
If Safari cannot enable them, a trusted HTTPS host with isolation headers is
required. The application reports this rather than repeatedly reloading.

## Acceptance

- Confirm readable native menus, Cube, grid and properties in landscape and portrait.
- In the completion candidate, drag with two fingers to orbit the 3D view and
  spread/pinch to zoom. Confirm the Cube stays in place and a subsequent
  one-finger tap selects normally. These gestures follow Blender's trackpad
  keymap; Shift plus the two-finger drag pans with the default preferences.
- Without a physical keyboard, tap a Blender text field, choose **Keyboard** in
  the header, enter text, and use Enter or Done. Check a filename and a Unicode
  object name. Ctrl/Shift/Alt and editing keys are available in that panel.
- With a keyboard, move the Cube using `G`, `X`, `1`, Enter. Cancel another transform
  with Escape, then confirm touch selection and the trackpad input you use.
- Subdivide or bevel a mesh, evaluate a geometry-node modifier, and animate a pose.
- Save a real project under `/projects` through Blender. Export a backup with the
  header control. Import a folder containing a project and its relative textures;
  open that project in Blender and verify the assets resolve.
- Render a small scene with a render engine listed as validated in the build's
  acceptance record, and export its image. A solid viewport alone is not rendering
  acceptance. Do not infer support for an unvalidated engine from its menu entry.
- Switch apps, lock/unlock the iPad and rotate it. Confirm input, redraw and the
  saved project remain usable after returning.
- Export a backup, then close Blender, stop WorldWideWeb and disable networking.
  Reopen the Home Screen app. Verify the actual editor starts and opens the saved
  project with the edited transform and assets intact.

If anything fails, download **Device report** from the header or error screen.
Report the first failing step and the exact error. Saved-project export remains
available from the error screen even if Blender cannot acquire an adapter.
Browser storage can still be evicted: exported backups are the recovery copy.
