// Fixed virtual paths for the browser background application. All resources
// are packaged locally; this does not depend on the host machine's filesystem.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  ENV['PYTHONHOME'] = '/python';
  ENV['BLENDER_SYSTEM_PYTHON'] = '/python';
  ENV['BLENDER_SYSTEM_RESOURCES'] = '/blender';
  ENV['BLENDER_SYSTEM_SCRIPTS'] = '/blender/scripts';
  ENV['BLENDER_SYSTEM_DATAFILES'] = '/blender/datafiles';
  ENV['XDG_CACHE_HOME'] = '/cache';
  // OIIO constructs its default pool before applying Blender's --threads
  // override. Avoid creating a hardware-sized pool and synchronously joining
  // workers that the browser has not yet had an opportunity to start.
  ENV['OPENIMAGEIO_THREADS'] = Module['browserLowResource'] ? '1' : '2';
  FS.mkdirTree('/cache');
});

// Asyncify rewinds outside callMain's initial exception handler. Register a
// completion handler before the first wait resolves, including normal exit.
Module['runBlenderMain'] = async function (args) {
  try {
    const result = callMain(args);
    if (typeof Asyncify !== 'undefined' && Asyncify.currData) {
      return await Asyncify.whenDone();
    }
    return result;
  } catch (error) {
    if (error instanceof ExitStatus && error.status === 0) return 0;
    if (error === 'unwind' && keepRuntimeAlive()) return;
    throw error;
  }
};

// Stop scheduling draws while the page is suspended or its device is lost.
// The filesystem remains available for downloading already-saved projects.
let blenderLoopPaused = false;
Module['pauseBlenderLoop'] = function () {
  if (blenderLoopPaused) return;
  // A paused scheduler releases its own keepalive token. Hold one explicitly
  // so EXIT_RUNTIME cannot run Blender's static destructors during suspension
  // or destroy project recovery state after GPU loss.
  Module['runtimeKeepalivePush']();
  blenderLoopPaused = true;
  Module['pauseMainLoop']?.();
};
Module['resumeBlenderLoop'] = function () {
  if (!blenderLoopPaused) return;
  Module['resumeMainLoop']?.();
  blenderLoopPaused = false;
  Module['runtimeKeepalivePop']();
};

// Read the internal heap from its own generated scope. Do not access Module.HEAPU8:
// unexported Emscripten symbols can have getters which abort the application.
Module['getBlenderMemoryBytes'] = function () { return HEAPU8.byteLength; };
