// Forward only the explicit runtime path selectors used by the native CLI
// integration tests. No credentials or general process environment are copied.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  for (const key of ['BLENDER_SYSTEM_RESOURCES', 'BLENDER_SYSTEM_SCRIPTS', 'BLENDER_SYSTEM_DATAFILES', 'BLENDER_SYSTEM_PYTHON', 'PYTHONHOME', 'XDG_CACHE_HOME']) {
    if (typeof process !== 'undefined' && process.env[key]) ENV[key] = process.env[key];
  }
});
