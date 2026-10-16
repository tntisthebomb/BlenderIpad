// SPDX-License-Identifier: GPL-2.0-or-later
// No UI-thread timers: a dedicated worker waits on shared memory between saves.
'use strict';
const slots=['blender-startup-recovery-a.json','blender-startup-recovery-b.json'];
let handles=[],slot=0,attempt=null,checkpoint=null,lastHeartbeat=0,maxGap=0,stopped=false,visible=true;
let control=null,payload=null,lastSequence=-1;
function checksum(text){let value=2166136261;for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619)>>>0;return value.toString(16);}
function readShared(){
  const before=Atomics.load(control,0);
  if(before===lastSequence||(before&1))return;
  const length=Atomics.load(control,1);
  if(length<1||length>payload.length)return;
  const bytes=payload.slice(0,length);
  if(before!==Atomics.load(control,0))return;
  const message=JSON.parse(new TextDecoder().decode(bytes));
  lastSequence=before;checkpoint=message.checkpoint;lastHeartbeat=message.lastHeartbeat;visible=message.visible;
  stopped=message.stopped;
}
function report(){
  const now=Date.now(),gap=visible?Math.max(0,now-lastHeartbeat):0;
  maxGap=Math.max(maxGap,gap);
  return {attemptId:attempt,storageBackend:'OPFS sync / shared wait',slotFile:slots[slot],observedAt:now,
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
onmessage=async event=>{
  const message=event.data;
  if(message.kind!=='start')return;
  attempt=message.attemptId;control=new Int32Array(message.shared,0,4);payload=new Uint8Array(message.shared,16);
  try {
    readShared();
    const directory=await navigator.storage.getDirectory();
    for(const name of slots){
      const file=await directory.getFileHandle(name,{create:true});
      handles.push(await file.createSyncAccessHandle());
    }
    if(!persist())return;
    postMessage({kind:'ready',attemptId:attempt});
    // WebKit may delay worker timer delivery while the page is busy. Waiting
    // here uses the worker's own thread. Checkpoints and heartbeats arrive in
    // shared memory, so this loop does not depend on its message event loop.
    while(!stopped){
      Atomics.wait(control,2,0,1000);
      readShared();
      if(!persist())return;
    }
    postMessage({kind:'stopped',attemptId:attempt});
  } catch(error){postMessage({kind:'storage-error',message:String(error)});}
  finally {for(const handle of handles)try{handle.close();}catch{}close();}
};
