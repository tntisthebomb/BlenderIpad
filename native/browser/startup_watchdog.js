// SPDX-License-Identifier: GPL-2.0-or-later
// A small independent recovery recorder. It never loads Blender or its module.
'use strict';
const DATABASE='blender-startup-recovery-v1',STORE='attempts';
let database=null,attempt=null,checkpoint=null,lastHeartbeat=0,maxGap=0,writing=false,stopped=false,visible=true;
const opened=new Promise((resolve,reject)=>{
  const request=indexedDB.open(DATABASE,1);
  request.onupgradeneeded=()=>request.result.createObjectStore(STORE);
  request.onsuccess=()=>{database=request.result;resolve(database);};
  request.onerror=()=>reject(request.error);
});
// Keep a handled Promise even if storage is unavailable before the first message.
opened.catch(error=>postMessage({kind:'storage-error',message:String(error)}));
function report(){
  const now=Date.now(),gap=visible?Math.max(0,now-lastHeartbeat):0;
  maxGap=Math.max(maxGap,gap);
  return {attemptId:attempt,observedAt:now,lastHeartbeatAgeMs:gap,maxHeartbeatGapMs:maxGap,
    observedElapsedSeconds:checkpoint?.startedAt?Math.round((now-checkpoint.startedAt)/1000):null,
    lastReportedPageVisible:visible,ended:stopped,checkpoint};
}
async function persist(){
  if(!attempt||writing)return;
  writing=true;
  try {
    const db=await opened,record=report();
    await new Promise((resolve,reject)=>{
      const transaction=db.transaction(STORE,'readwrite');
      transaction.objectStore(STORE).put(record,'last');
      transaction.oncomplete=resolve;
      transaction.onerror=()=>reject(transaction.error);
      transaction.onabort=()=>reject(transaction.error||Error('Recovery transaction aborted'));
    });
    postMessage({kind:'sample',attemptId:attempt,maxHeartbeatGapMs:record.maxHeartbeatGapMs,
      lastHeartbeatAgeMs:record.lastHeartbeatAgeMs,observedAt:record.observedAt});
  } catch(error){postMessage({kind:'storage-error',message:String(error)});}
  finally{writing=false;}
}
const timer=setInterval(()=>persist(),1000);
onmessage=async event=>{
  const message=event.data;
  if(message.kind==='start'){
    attempt=message.attemptId;lastHeartbeat=Date.now();checkpoint=message.checkpoint;visible=checkpoint?.pageVisible!==false;
    try{await opened;await persist();postMessage({kind:'ready',attemptId:attempt});}
    catch(error){postMessage({kind:'storage-error',message:String(error)});}
  } else if(message.kind==='visibility'){
    visible=message.visible;lastHeartbeat=Date.now();
  } else if(message.kind==='heartbeat'){
    if(visible)maxGap=Math.max(maxGap,Date.now()-lastHeartbeat);lastHeartbeat=Date.now();
  } else if(message.kind==='native-line'){
    if(checkpoint){
      checkpoint.lines=(checkpoint.lines??[]).concat(message.line).slice(-4);
      checkpoint.progressSequence=message.progressSequence;
      checkpoint.elapsedSeconds=message.elapsedSeconds;
    }
  } else if(message.kind==='checkpoint'){
    checkpoint=message.checkpoint;
  } else if(message.kind==='stop'){
    checkpoint=message.checkpoint;stopped=true;clearInterval(timer);
    // Wait for the single outstanding transaction before saving final state.
    while(writing)await new Promise(resolve=>setTimeout(resolve,10));
    await persist();database?.close();postMessage({kind:'stopped',attemptId:attempt});close();
  }
};
