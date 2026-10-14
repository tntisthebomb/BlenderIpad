# Blender on iPad: browser port

Goal: run the latest stable Blender locally on an iPad as an installable, offline PWA, with physical keyboard input and no jailbreak or alternative app store.

For resumed sessions, [RECOVERY.md](RECOVERY.md) identifies the verified source,
latest successful editor workflow, recovered artifacts and remaining work.

**Current status: the real Blender 5.2.2 editor passes Chromium acceptance.** Its solid viewport, grid, fonts and native UI render; physical-keyboard transforms and touch selection work; native projects save, persist and reload after an offline application restart. This is an experimental port: render-engine validation, disabled optional features and acceptance on the target iPad remain outstanding. The older `ipad-workbench` download is still a separate math demo. See [BROWSER_PORT.md](BROWSER_PORT.md) for scope and reproducible commands.

## Experimental editor build

The actual editor is built separately from the legacy math workbench:

Use a Linux builder with at least 16 GiB RAM. Compilation fits in 8 GiB, but
full-editor Asyncify linking exceeded that limit even with staged optimization.
The editor CI workflow provides separate graphics and CPU Cycles candidates;
each must pass its actual engine render checks before producing an accepted ZIP.

```sh
python3 scripts/build_browser_platform.py
python3 scripts/build_browser_core_deps.py
python3 scripts/build_browser_python.py
python3 scripts/build_browser_python_probe.py
python3 scripts/build_browser_shaderc.py
python3 scripts/test_browser_shaderc.py
python3 scripts/build_browser_tint.py
python3 scripts/test_browser_tint.py
python3 scripts/build_blender_core.py --editor
python3 scripts/test_blender_core.py --webgpu
python3 scripts/build_blender_core_browser.py --editor
python3 -m venv .cache/browser-tests
.cache/browser-tests/bin/python -m pip install playwright==1.62.0 Pillow==12.0.0
python3 scripts/validate_blender_editor.py
python3 scripts/package_blender_editor.py
```

Acceptance requires Chromium with a working WebGPU adapter; set `CHROMIUM_PATH` when necessary. Packaging rejects changed assets or fixtures after acceptance. It writes `dist/BlenderIpad-5.2.2-editor-preview.zip` and its corresponding `-source.tar.gz`, containing prepared Blender, dependency sources, runtime sources, overlays, licenses and rebuild instructions. These names describe local outputs, not an already published release.

Serve the extracted editor assets over HTTPS with COOP/COEP headers, or use a
trusted localhost origin in WorldWideWeb. Follow [IPAD_ACCEPTANCE.md](IPAD_ACCEPTANCE.md)
for the target iPad: keep the server's port/path and use `localhost` or
`127.0.0.1`, wait for the real editor and offline-ready message, then install and
test the Home Screen app. That route still requires physical-device acceptance.
WebGPU, shared memory and cross-origin isolation are required. Plain HTTP
`users-ipad.local` cannot provide those requirements. GitHub Pages cannot set
the required headers directly; its existing workflow builds the legacy math
demo. Computation is local once the assets load. Initial shader compilation can
take several minutes. Export backups because browser storage can be evicted.

The combined experimental editor is distributed under GPL-3.0-or-later, compatible with Blender's GPL-2.0-or-later licensing and its Apache-2.0 shader translation dependencies. See [THIRD_PARTY.md](THIRD_PARTY.md).

## Legacy math workbench


The target is **Blender 5.2.2 LTS**, the newest stable version tag observed in the official [Blender source mirror](https://github.com/blender/blender/tree/v5.2.2) on October 12, 2026. Its version header says `502`, patch `2`, cycle `release`, suffix `LTS`. The official download page could not be accessed from this environment; the release selection was verified against source tags and the source version header. The exact source commit and compiler artifact hash are in [port.lock.json](port.lock.json). The project stays on that reproducible release until an explicit version update.

## Build and run

Build host: Linux x86-64, Python 3.12+, Git, and Node.js 20+ for tests. The compiler downloads through HTTPS from GitHub; no system package installation is needed. WASM output runs independently of the build host architecture.

```sh
cd /workspace/BlenderIpad
python3 scripts/build_kernel.py
node --test tests/math.test.mjs
python3 scripts/serve.py --port 8080
```

`build_kernel.py` prepares a source checkout under `.cache/blender`, verifies its exact commit and clean state, verifies the WASI SDK archive checksum, and builds:

- `web/engine/blender-math.wasm`: approximately 159 KiB, with 2 MiB initial linear memory and a 16 MiB maximum for this math-only milestone.
- `web/engine/build.json`: version, source commit, scope and input/output hashes.
- `web/engine/source.tar.gz`: corresponding source, upstream license notices, wrapper and a standalone rebuild script. After extraction, set `WASI_SDK_PATH` to the WASI SDK 25 directory and run `python3 rebuild.py`.

The initial Git clone intentionally leaves LFS assets as pointers. The math build does not use them. The full-browser configuration script separately materializes and verifies the real startup asset in a patched source copy; dependencies must be cross-compiled rather than borrowed from the build host.

The server listens only on the build machine's loopback interface. **To install on an iPad, deploy the contents of `web/` to an HTTPS static host.** No backend or remote Blender process is required by this milestone. Hosting needs `.wasm` served as `application/wasm`, `.js` as JavaScript, and the manifest as `application/manifest+json`. Serve `sw.js` without long-lived HTTP caching. For future WASM threads, preserve these headers on the app and assets:

```text
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
```

The current math build is single-threaded. Shared memory is detected but not used. The wireframe uses Canvas 2D; availability of WebGPU does not mean Blender has a working WebGPU backend.

Open the hosted page in Safari, choose **Share → Add to Home Screen**, and wait for **Downloaded · ready for offline reload** before disconnecting. The service worker caches the app, WASM, build metadata, license, and corresponding source. Storage is subject to browser eviction: offline availability is verified for the current cache, not guaranteed indefinitely. Bump the service worker cache version when deploying changed assets so existing installations receive a coherent update.

## Legacy math demo in WorldWideWeb

For the actual Blender editor, use the editor artifact and
[IPAD_ACCEPTANCE.md](IPAD_ACCEPTANCE.md). The instructions below apply to the
older math prototype.

Download the newest successful build's `ipad-workbench` artifact from the repository's Actions tab. Extract it in Files. Select the directory containing `index.html` as WorldWideWeb's root and start serving. Open the supplied address in Safari and keep WorldWideWeb running. Browser scripts use `.js` because some local servers do not recognize the `.mjs` module extension.

An HTTP `users-ipad.local` or Wi-Fi address can run the math test without Internet, but it is not a secure context for service-worker installation. In that mode the status says **Local server mode · keep WorldWideWeb running**; files are served by the local app each time. HTTPS or a browser-recognized loopback address is needed for the independent PWA offline cache. Closing or suspending the local server can interrupt access.

A blank viewport stuck on Loading Blender math means startup did not complete. The updated page reports script-load, runtime and missing-engine errors directly in Source Check. A successful startup displays **Blender math running locally**, five passed source checks, and a wireframe cube. This is a math test, not the Blender editor or render engines.

## GitHub Pages deployment

The **Build iPad workbench** workflow in `.github/workflows/pages.yml` builds the pinned source, runs the seven WASM tests, and uploads a direct `ipad-workbench` ZIP containing `index.html`, browser scripts, engine and corresponding source. Normal pushes do not attempt Pages deployment. Official GitHub Actions are pinned to exact commits.

For optional HTTPS publication, run the workflow manually and select **deploy_pages**.

For initial setup, the repository's **Settings → Pages → Build and deployment → Source** must be **GitHub Actions**. An authorized administrator can enable this in the UI or via the Pages API. The workflow's default `GITHUB_TOKEN` cannot enable Pages for the first time. This is a prerequisite, not a completed deployment.

GitHub Pages cannot set custom COOP/COEP response headers. The current single-threaded milestone does not require them and still runs offline. A future full port using WASM threads will need a hosting strategy that supplies the required isolation behavior; the local server's headers do not automatically carry over to Pages.

## Touch and keyboard test

Use the Move, Rotate and Scale buttons, choose an axis with the X/Y/Z buttons, and tap − / + or drag in the viewport to adjust. Confirm keeps a change; Cancel restores the pose from before the operation. Dragging without choosing a mode moves along the selected axis and confirms when released. Touch interruption cancels a pending drag. The viewport and control panel suppress text selection and the iOS copy callout; text outside the workbench remains selectable.

Tap or click the viewport to focus the physical keyboard. Press `G`, `R` or `S`, choose `X`, `Y` or `Z`, then use arrow keys. `Enter` confirms, `Escape` cancels, and `Shift` makes finer adjustments. This is a small test harness around the compiled math routines; it does not implement Blender's complete shortcut system. System-reserved shortcuts remain controlled by iPadOS/Safari.

## Validation

```sh
node --test tests/math.test.mjs
python3 tests/browser_test.py
python3 tests/local_server_test.py
python3 tests/touch_test.py
```

The browser test requires the Python Playwright package and Chromium. It uses `/usr/lib/chromium/chromium` by default; set `CHROMIUM_PATH` for another installation. If those tools are absent, install them in a local virtual environment/browser directory rather than modifying the project sources. The onboarding machine already provides both.

Verified here:

- Seven WASM tests, including 256 transform/inverse round trips, rotations, interpolation, zero-vector normalization, singular-matrix handling and live Blender assertion failures.
- Actual WASM execution in Chromium; keyboard move/scale, cancellation and reset.
- Service worker installation and network-disabled reload, followed by another keyboard transform.
- Offline corresponding-source retrieval, isolation headers, and narrow-screen layout.
- The downloaded source bundle rebuilds and its resulting WASM passes the five browser math checks.

**Not verified here:** Safari/WebKit, installation on a physical iPad, background suspension, real iPad GPU limits, or render-engine behavior on the target device. The target device is an iPad 10th generation (A14, 4 GB RAM), running iPadOS 26. The user has verified the math workbench's keyboard controls on that device. iPadOS 26 provides Safari WebGPU support, but an adapter and its limits still need verification in a secure context on the actual device. An HTTP `.local` address does not provide that context.

The shader translation prerequisites now pass local tests: Blender’s actual GPU matrix library compiles through GLSL → SPIR-V → WGSL and executes through WebGPU, including the native C++ bindings. The integrated editor now also passes viewport and project acceptance; full render-engine validation remains outstanding. See [BROWSER_PORT.md](BROWSER_PORT.md) for reproducible commands and the remaining integration.

## Full-port work remaining

See [PORTING.md](PORTING.md) for the source-level requirements and acceptance checks. A successful math build does not establish that the full application can be compiled by changing a build flag.

Blender code and this project are GPL-2.0-or-later; see [LICENSE](LICENSE). Original source notices are retained in the source bundle. This project is unaffiliated with the Blender Foundation.
