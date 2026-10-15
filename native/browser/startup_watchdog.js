// SPDX-License-Identifier: GPL-2.0-or-later
// Worker-owned synchronous files remain writable while WebKit's UI is blocked.
'use strict';
const slots=['blender-startup-recovery-a.json','blender-startup-recovery-b.json'];
let handles=[],slot=0,attempt=null,checkpoint=null,lastHeartbeat=0,maxGap=0,stopped=false,visible=true;
function checksum(text){let value=2166136261;for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619)>>>0;return value.toString(16);}
const opened=(async()=>{
  const directory=await navigator.storage.getDirectory();
  for(const name of slots){
    const file=await directory.getFileHandle(name,{create:true});
    handles.push(await file.createSyncAccessHandle());
  }
  return handles;
})();
opened.catch(error=>{for(const handle of handles)try{handle.close();}catch{}postMessage({kind:'storage-error',message:String(error)});});
function report(){
  const now=Date.now(),gap=visible?Math.max(0,now-lastHeartbeat):0;
  maxGap=Math.max(maxGap,gap);
  return {attemptId:attempt,storageBackend:'OPFS sync',slotFile:slots[slot],observedAt:now,
    lastHeartbeatAgeMs:gap,maxHeartbeatGapMs:maxGap,
    observedElapsedSeconds:checkpoint?.startedAt?Math.round((now-checkpoint.startedAt)/1000):null,
    lastReportedPageVisible:visible,ended:stopped,checkpoint};
}
function persist(){
  if(!attempt||handles.length!==2)return false;
  try {
    const record=report(),payload=JSON.stringify(record);
    const bytes=new TextEncoder().encode(JSON.stringify({version:2,payload,checksum:checksum(payload)}));
    const handle=handles[slot];
    const written=handle.write(bytes,{at:0});
    if(written!==bytes.byteLength)throw Error('Incomplete recovery write');
    handle.truncate(bytes.byteLength);handle.flush();slot=1-slot;
    postMessage({kind:'sample',attemptId:attempt,maxHeartbeatGapMs:record.maxHeartbeatGapMs,
      lastHeartbeatAgeMs:record.lastHeartbeatAgeMs,observedAt:record.observedAt});
    return true;
  } catch(error){postMessage({kind:'storage-error',message:String(error)});return false;}
}
const timer=setInterval(()=>{if(!stopped)persist();},1000);
onmessage=async event=>{
  const message=event.data;
  if(message.kind==='start'){
    attempt=message.attemptId;lastHeartbeat=Date.now();checkpoint=message.checkpoint;visible=checkpoint?.pageVisible!==false;
    try{await opened;const saved=persist();if(saved&&!stopped)postMessage({kind:'ready',attemptId:attempt});}
    catch(error){postMessage({kind:'storage-error',message:String(error)});}
  } else if(message.kind==='visibility'){
    visible=message.visible;lastHeartbeat=Date.now();
  } else if(message.kind==='heartbeat'){
    if(visible)maxGap=Math.max(maxGap,Date.now()-lastHeartbeat);lastHeartbeat=Date.now();
  } else if(message.kind==='native-line'){
    if(checkpoint){checkpoint.lines=(checkpoint.lines??[]).concat(message.line).slice(-4);
      checkpoint.progressSequence=message.progressSequence;checkpoint.elapsedSeconds=message.elapsedSeconds;}
  } else if(message.kind==='checkpoint'){
    checkpoint=message.checkpoint;
  } else if(message.kind==='stop'){
    checkpoint=message.checkpoint;stopped=true;clearInterval(timer);
    try{await opened;persist();}catch{}
    for(const handle of handles)try{handle.close();}catch{}
    postMessage({kind:'stopped',attemptId:attempt});close();
  }
};
