# Third-party source used in the browser port

`native/browser/GHOST_SystemWeb.cc`, `GHOST_SystemWeb.hh` and `GHOST_WindowWeb.hh` are adapted from [HeyPuter/blender](https://github.com/HeyPuter/blender/tree/6b031d3d41c392883e3c495aa72343e10d15b43d/intern/ghost/intern), commit `6b031d3d41c392883e3c495aa72343e10d15b43d`. Their original Blender Authors copyright notices and GPL-2.0-or-later license identifiers are retained. The project GPL license is in `LICENSE`.

That reference fork identifies itself as Blender 5.3 alpha. We imported only these browser platform files and adapted them against **stable Blender 5.2.2**; we did not replace the stable core with the alpha fork or import its unvalidated graphics/shader error-recovery code.

Our changes include truthful capability reporting, explicit failure for unimplemented presentation, stable-version GHOST factory registration, native touch events, input focus and modifier handling, UTF-8 key text, redraw events, and window/callback cleanup. The backend is currently an input/window platform with `GHOST_kDrawingContextTypeNone`; it is not a renderer.

The exploratory build recipe repository [HeyPuter/blender-wasm](https://github.com/HeyPuter/blender-wasm/tree/f8f811929f8a5bc218e04944cf2dff25eeeccbf3) informed the public upstream LFS endpoint configuration. Its claims of rendering/UI support have not been adopted as our validation results.

Blender's original GHOST, allocator, logging and dependency code is fetched from the immutable release pin in `port.lock.json`. Dependency archive hashes are taken from that release's `build_files/build_environment/cmake/versions.cmake` and are retained in `browser-port.lock.json`. No checksums or assertions are weakened to accept a build.
