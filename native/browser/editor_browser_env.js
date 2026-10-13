// Keep Blender's own filesystem paths durable across browser sessions.
Module['preRun'] ??= [];
Module['preRun'].push(function () {
  FS.mkdirTree('/projects');
  FS.mount(IDBFS, {autoPersist:true}, '/projects');
  addRunDependency('project-storage');
  FS.syncfs(true, function (error) {
    if (error) {
      abort('Unable to restore saved projects: ' + error);
      return;
    }
    ENV['HOME']='/projects';
    ENV['BLENDER_USER_CONFIG']='/projects/.blender/config';
    ENV['BLENDER_USER_SCRIPTS']='/projects/.blender/scripts';
    ENV['BLENDER_USER_EXTENSIONS']='/projects/.blender/extensions';
    FS.mkdirTree('/projects/.blender/config');
    FS.mkdirTree('/projects/.blender/scripts');
    FS.mkdirTree('/projects/.blender/extensions');
    Module['projectStorageReady']=true;
    removeRunDependency('project-storage');
  });
});
