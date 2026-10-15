Blender iPad startup and offline-update helpers

These small HTML pages do not contain the Blender engine.

ipad-startup.html: engine-free device check (ipad-preflight-v2). Open at
http://localhost:8080/ipad-startup.html. Browser details appear immediately;
Check graphics support only reads an adapter. It does not create a GPU device,
load Blender or install its service worker. Copy/select/download its report.
This page can be served by itself without downloading Blender.

ipad-update.html: installs the complete engine build already in your server
folder without compiling or starting Blender. It is useful when an older
cached editor freezes and must be replaced. It is not a replacement engine.
Use only after extracting the supplied replacement build into WorldWideWeb's
folder containing index.html, service-worker.js and blender-core files.
Copy ipad-update.html into that folder and open
http://localhost:8080/ipad-update.html directly, rather than opening index.html.
Close other Blender tabs/Home Screen windows, keep WorldWideWeb running, and
choose Install or update offline files. It downloads/cache-stores large engine
files but never executes them. If the update is waiting, close this updater tab
and every Blender tab/window, then reopen the normal Blender address. This lets
the fully installed new worker activate without mixing old/new engine files.

Preserve your actual server port/path. Do not clear site data to force updates;
that could remove saved projects. Failed downloads preserve the old cache.
Neither helper proves that a full build is usable on the physical iPad.
If the device becomes sluggish, close any running Blender editor first.

SPDX-License-Identifier: GPL-3.0-or-later
Complete helper source is included in each readable HTML file.
