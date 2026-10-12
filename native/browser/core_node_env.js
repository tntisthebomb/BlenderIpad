// Forward only the explicit runtime path selectors used by the native CLI
// integration tests. No credentials or general process environment are copied.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  for (const key of ['BLENDER_SYSTEM_SCRIPTS', 'BLENDER_SYSTEM_DATAFILES', 'PYTHONHOME']) {
    if (typeof process !== 'undefined' && process.env[key]) ENV[key] = process.env[key];
  }
});
