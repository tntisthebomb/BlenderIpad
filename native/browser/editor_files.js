// Browser file transfer around Blender's own project files and file browser.
function syncProjects() {
  return new Promise((resolve,reject)=>blenderEditor.FS.syncfs(false,error=>error ? reject(error) : resolve()));
}
function projectFiles(directory='/projects') {
  const fs=blenderEditor.FS;
  const result=[];
  for (const name of fs.readdir(directory)) {
    if (name==='.' || name==='..' || name==='.blender') continue;
    const path=directory+'/'+name;
    const stat=fs.stat(path);
    if (fs.isDir(stat.mode)) result.push(...projectFiles(path));
    else result.push(path);
  }
  return result;
}
const fileMessage=document.getElementById('file-message');
document.getElementById('import-files').addEventListener('change',async event=>{
  try {
    if (!window.blenderEditor) throw new Error('Blender is still loading.');
    for (const file of event.target.files) {
      const base=file.name.replace(/[\\/]/g,'_');
      let path='/projects/'+base;
      let number=1;
      while (blenderEditor.FS.analyzePath(path).exists) {
        const dot=base.lastIndexOf('.');
        path='/projects/'+(dot>0 ? base.slice(0,dot)+'-'+number+base.slice(dot) : base+'-'+number);
        number++;
      }
      const bytes=new Uint8Array(await file.arrayBuffer());
      blenderEditor.FS.writeFile(path,bytes,{canOwn:true});
    }
    await syncProjects();
    fileMessage.textContent='Imported. Choose File → Open in Blender to open a project.';
  } catch(error) { fileMessage.textContent=String(error); }
  finally { event.target.value='';document.getElementById('canvas').focus({preventScroll:true}); }
});
document.getElementById('export-files').addEventListener('click',()=>{
  try {
    if (!window.blenderEditor) throw new Error('Blender is still loading.');
    const paths=projectFiles();
    if (!paths.length) throw new Error('Save a project in Blender first, then export it here.');
    const select=document.getElementById('saved-files');
    select.replaceChildren();
    for (const path of paths.sort()) {
      const option=document.createElement('option');
      option.value=path;option.textContent=path.slice('/projects/'.length);
      select.append(option);
    }
    document.getElementById('file-dialog').showModal();
  } catch(error) { fileMessage.textContent=String(error); }
});
document.getElementById('download-file').addEventListener('click',async()=>{
  try {
    await syncProjects();
    const path=document.getElementById('saved-files').value;
    const bytes=blenderEditor.FS.readFile(path);
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));
    const link=document.createElement('a');
    link.href=url;link.download=path.split('/').pop();document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
    document.getElementById('file-dialog').close();
    fileMessage.textContent='Exported '+path.split('/').pop();
  } catch(error) { fileMessage.textContent=String(error); }
});
document.getElementById('close-files').addEventListener('click',()=>{
  document.getElementById('file-dialog').close();document.getElementById('canvas').focus({preventScroll:true});
});
