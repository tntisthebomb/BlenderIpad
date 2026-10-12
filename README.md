# Blender on iPad: browser port

Goal: run the latest stable Blender locally on an iPad as an installable, offline PWA, with physical keyboard input and no jailbreak or alternative app store.

**Current status: a tested first porting milestone, not full Blender.** The workbench compiles unmodified Blender math implementation files into WebAssembly. It displays a wireframe transformation test and accepts keyboard move/rotate/scale commands. Blender's editor, Eevee/Cycles, `.blend` I/O, Python, sculpting and modifiers are not ported or exposed by this milestone.

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

The initial Git clone intentionally leaves LFS assets as pointers. The math build does not use them. A future full Blender build must fetch the real LFS assets and separately cross-compile its dependencies; this is not a prepared full desktop Blender checkout.

The server listens only on the build machine's loopback interface. **To install on an iPad, deploy the contents of `web/` to an HTTPS static host.** No backend or remote Blender process is required by this milestone. Hosting needs `.wasm` served as `application/wasm`, `.js` as JavaScript, and the manifest as `application/manifest+json`. Serve `sw.js` without long-lived HTTP caching. For future WASM threads, preserve these headers on the app and assets:

```text
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
```

The current math build is single-threaded. Shared memory is detected but not used. The wireframe uses Canvas 2D; availability of WebGPU does not mean Blender has a working WebGPU backend.

Open the hosted page in Safari, choose **Share → Add to Home Screen**, and wait for **Downloaded · ready for offline reload** before disconnecting. The service worker caches the app, WASM, build metadata, license, and corresponding source. Storage is subject to browser eviction: offline availability is verified for the current cache, not guaranteed indefinitely. Bump the service worker cache version when deploying changed assets so existing installations receive a coherent update.

## WorldWideWeb on iPad

Download the newest successful build's `ipad-workbench` artifact from the repository's Actions tab. Extract it in Files. Select the directory containing `index.html` as WorldWideWeb's root and start serving. Open the supplied address in Safari and keep WorldWideWeb running. Browser scripts use `.js` because some local servers do not recognize the `.mjs` module extension.

An HTTP `users-ipad.local` or Wi-Fi address can run the math test without Internet, but it is not a secure context for service-worker installation. In that mode the status says **Local server mode · keep WorldWideWeb running**; files are served by the local app each time. HTTPS or a browser-recognized loopback address is needed for the independent PWA offline cache. Closing or suspending the local server can interrupt access.

A blank viewport stuck on Loading Blender math means startup did not complete. The updated page reports script-load, runtime and missing-engine errors directly in Source Check. A successful startup displays **Blender math running locally**, five passed source checks, and a wireframe cube. This is a math test, not the Blender editor or render engines.

## GitHub Pages deployment

The **Build iPad workbench** workflow in `.github/workflows/pages.yml` builds the pinned source, runs the seven WASM tests, and uploads a direct `ipad-workbench` ZIP containing `index.html`, browser scripts, engine and corresponding source. Normal pushes do not attempt Pages deployment. Official GitHub Actions are pinned to exact commits.

For optional HTTPS publication, run the workflow manually and select **deploy_pages**.

For initial setup, the repository's **Settings → Pages → Build and deployment → Source** must be **GitHub Actions**. An authorized administrator can enable this in the UI or via the Pages API. The workflow's default `GITHUB_TOKEN` cannot enable Pages for the first time. This is a prerequisite, not a completed deployment.

GitHub Pages cannot set custom COOP/COEP response headers. The current single-threaded milestone does not require them and still runs offline. A future full port using WASM threads will need a hosting strategy that supplies the required isolation behavior; the local server's headers do not automatically carry over to Pages.

## Keyboard test

Tap or click the viewport to focus it. Press `G`, `R` or `S`, choose `X`, `Y` or `Z`, then use arrow keys. `Enter` confirms, `Escape` cancels, and `Shift` makes finer adjustments. This is a small test harness around the compiled math routines; it does not implement Blender's complete shortcut system. System-reserved shortcuts remain controlled by iPadOS/Safari.

## Validation

```sh
node --test tests/math.test.mjs
python3 tests/browser_test.py
python3 tests/local_server_test.py
```

The browser test requires the Python Playwright package and Chromium. It uses `/usr/lib/chromium/chromium` by default; set `CHROMIUM_PATH` for another installation. If those tools are absent, install them in a local virtual environment/browser directory rather than modifying the project sources. The onboarding machine already provides both.

Verified here:

- Seven WASM tests, including 256 transform/inverse round trips, rotations, interpolation, zero-vector normalization, singular-matrix handling and live Blender assertion failures.
- Actual WASM execution in Chromium; keyboard move/scale, cancellation and reset.
- Service worker installation and network-disabled reload, followed by another keyboard transform.
- Offline corresponding-source retrieval, isolation headers, and narrow-screen layout.
- The downloaded source bundle rebuilds and its resulting WASM passes the five browser math checks.

**Not verified:** Safari/WebKit, installation on a physical iPad, background suspension, real iPad GPU limits, or any full Blender workflow. The target device is an iPad 10th generation (A14, 4 GB RAM); its iPadOS version has not been supplied. Check Safari's WebGPU adapter availability on the actual device before committing to a graphics implementation.

## Full-port work remaining

See [PORTING.md](PORTING.md) for the source-level requirements and acceptance checks. A successful math build does not establish that the full application can be compiled by changing a build flag.

Blender code and this project are GPL-2.0-or-later; see [LICENSE](LICENSE). Original source notices are retained in the source bundle. This project is unaffiliated with the Blender Foundation.
