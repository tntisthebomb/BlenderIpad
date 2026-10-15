// Forward only the explicit runtime path selectors used by the native CLI
// integration tests. No credentials or general process environment are copied.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  // Match the browser profile's bounded image-I/O workers before constructors
  // create pools; the CLI --threads override runs later.
  ENV['OPENIMAGEIO_THREADS'] = '2';
  for (const key of ['BLENDER_SYSTEM_RESOURCES', 'BLENDER_SYSTEM_SCRIPTS', 'BLENDER_SYSTEM_DATAFILES', 'BLENDER_SYSTEM_PYTHON', 'PYTHONHOME', 'XDG_CACHE_HOME']) {
    if (typeof process !== 'undefined' && process.env[key]) ENV[key] = process.env[key];
  }
});
