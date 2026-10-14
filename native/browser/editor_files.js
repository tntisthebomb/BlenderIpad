// Browser file transfer around Blender's own project files and file browser.
let projectSync=Promise.resolve();
function syncProjects() {
  const next=projectSync.catch(()=>{}).then(()=>new Promise((resolve,reject)=>
    blenderEditor.FS.syncfs(false,error=>error ? reject(error) : resolve())));
  projectSync=next;
  return next;
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
let exportFromStorage=false;
function savedProjectStore(operation) {
  // Read the pinned IDBFS schema without booting Blender. This preserves a
  // backup route even when an adapter or engine startup is unavailable.
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open('/projects');
    request.onupgradeneeded=()=>request.transaction.abort();
    request.onerror=()=>reject(new Error('No saved project storage is available.'));
    request.onblocked=()=>reject(new Error('Close other Blender tabs and try again.'));
    request.onsuccess=()=>{
      const database=request.result;
      if (database.version!==21 || !database.objectStoreNames.contains('FILE_DATA')) {
        database.close();reject(new Error('Saved project storage has an unsupported format.'));return;
      }
      const transaction=database.transaction('FILE_DATA','readonly');
      let result;
      transaction.oncomplete=()=>{database.close();resolve(result);};
      transaction.onerror=()=>{database.close();reject(transaction.error);};
      operation(transaction.objectStore('FILE_DATA'),value=>result=value);
    };
  });
}
function storedProjectFiles() {
  return savedProjectStore((store,done)=>{
    const paths=[];
    const request=store.openCursor();
    request.onsuccess=()=>{
      const cursor=request.result;
      if (!cursor) {done(paths);return;}
      const path=String(cursor.key);
      if (path.startsWith('/projects/') && !path.startsWith('/projects/.blender/') &&
          (cursor.value.mode & 0o170000)===0o100000) paths.push(path);
      cursor.continue();
    };
  });
}
function storedProjectBytes(path) {
  return savedProjectStore((store,done)=>{
    const request=store.get(path);
    request.onsuccess=()=>done(request.result?.contents);
  });
}
async function downloadDeviceReport() {
  try {
    const installation=await new Promise(resolve=>{
      const controller=navigator.serviceWorker?.controller;
      if (!controller) {resolve(null);return;}
      const channel=new MessageChannel();
      const timer=setTimeout(()=>{channel.port1.close();resolve(null);},1000);
      channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();resolve(event.data);};
      controller.postMessage({type:'BUILD_INFO'},[channel.port2]);
    });
    const report={...window.blenderDeviceReport,
      installation,
      started:document.body.dataset.started==='true',error:document.body.dataset.error || null,
      persistentStorage:document.body.dataset.persistentStorage || 'unknown',
      memoryBytes:window.blenderEditor?.HEAPU8?.byteLength || null,
      storage:navigator.storage?.estimate ? await navigator.storage.estimate() : null};
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const link=document.createElement('a');
    link.href=url;link.download='BlenderIpad-device-report.json';document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  } catch(error) {fileMessage.textContent=String(error);}
}
document.getElementById('device-report').addEventListener('click',downloadDeviceReport);
document.getElementById('error-device-report').addEventListener('click',downloadDeviceReport);
async function importFiles(event) {
  const created=[];
  try {
    if (!window.blenderEditor) throw new Error('Blender is still loading.');
    for (const file of event.target.files) {
      // Folder selection preserves texture and linked-project paths. Reject
      // traversal or attempts to overwrite the application's own preferences.
      const relative=file.webkitRelativePath || file.name.replace(/[\\/]/g,'_');
      const parts=relative.split('/');
      if (parts.some(part=>!part || part==='.' || part==='..') || parts[0]==='.blender') {
        throw new Error('Invalid import path: '+relative);
      }
      const base=parts.pop();
      const directory='/projects/'+parts.join('/');
      blenderEditor.FS.mkdirTree(directory);
      let path=directory+'/'+base;
      let number=1;
      while (blenderEditor.FS.analyzePath(path).exists) {
        const dot=base.lastIndexOf('.');
        // Renaming a folder's existing files would silently break its links.
        // Keep the current project intact and ask for a separate folder.
        if (file.webkitRelativePath) throw new Error('Folder already contains '+relative+'. Rename the imported folder first.');
        path=directory+'/'+(dot>0 ? base.slice(0,dot)+'-'+number+base.slice(dot) : base+'-'+number);
        number++;
      }
      const bytes=new Uint8Array(await file.arrayBuffer());
      created.push(path);
      blenderEditor.FS.writeFile(path,bytes,{canOwn:true});
    }
    await syncProjects();
    fileMessage.textContent='Imported. Choose File → Open in Blender to open a project.';
  } catch(error) {
    for (const path of created) {
      if (blenderEditor.FS.analyzePath(path).exists) blenderEditor.FS.unlink(path);
    }
    try { await syncProjects(); } catch (_) {}
    fileMessage.textContent='Import failed; existing files were kept. '+String(error);
  }
  finally { event.target.value='';document.getElementById('canvas').focus({preventScroll:true}); }
}
document.getElementById('import-files').addEventListener('change',importFiles);
document.getElementById('import-folder').addEventListener('change',importFiles);
document.getElementById('export-files').addEventListener('click',async()=>{
  try {
    exportFromStorage=!window.blenderEditor;
    const paths=exportFromStorage ? await storedProjectFiles() : projectFiles();
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
    // Export must still work if persistent storage is full or unavailable.
    let storageError=null;
    if (!exportFromStorage) {
      try { await syncProjects(); } catch(error) { storageError=error; }
    }
    const path=document.getElementById('saved-files').value;
    const bytes=exportFromStorage ? await storedProjectBytes(path) : blenderEditor.FS.readFile(path);
    if (!bytes) throw new Error('The saved file is no longer available.');
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));
    const link=document.createElement('a');
    link.href=url;link.download=path.split('/').pop();document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
    document.getElementById('file-dialog').close();
    fileMessage.textContent='Exported '+path.split('/').pop()+(exportFromStorage ? '. Recovered saved copy from browser storage.' :
      (storageError ? '. Browser storage failed; keep this backup.' : ''));
  } catch(error) { fileMessage.textContent=String(error); }
});
document.getElementById('close-files').addEventListener('click',()=>{
  document.getElementById('file-dialog').close();document.getElementById('canvas').focus({preventScroll:true});
});
