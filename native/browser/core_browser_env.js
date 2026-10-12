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
  FS.mkdirTree('/cache');
});
