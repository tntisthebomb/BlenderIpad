(()=>{
// SPDX-License-Identifier: GPL-2.0-or-later
// Deliberately slow real GPU calls; measure from explicit launch through the first frame.

window.firstFrameProfile={pipelines:0,rafTicks:0,timerTicks:0,injectedDelayMs:60,maxHeartbeatGapMs:0,maxLaunchHeartbeatGapMs:0,maxPreWarmupHeartbeatGapMs:0,nativeSetupMarkers:[],longGaps:[]};
const metrics=firstFrameProfile;
let statsObject;
Object.defineProperty(window,'blenderStartupStats',{configurable:true,
 get(){return statsObject;},set(value){
  statsObject=value;
  const start=value.start;
  value.start=function(...args){
   if(!metrics.launchStartedAbsoluteTime){
    metrics.launchStartedAt=performance.now();
    metrics.launchStartedAbsoluteTime=performance.timeOrigin+metrics.launchStartedAt;
   }
   persistLaunch();
   return Reflect.apply(start,this,args);
  };
  const line=value.line;
  value.line=function(message){
   const text=String(message);
   if(!metrics.finishedAt&&(window.profileCaptureAll||/^(GPU initialization:|WEBGPU_CONTEXT|WGPU_SHADER_MS)/.test(text))&&metrics.nativeSetupMarkers.length<(window.profileCaptureAll?1000:40)){
    metrics.nativeSetupMarkers.push({atMs:performance.now(),text:text.slice(0,180)});
   }
   return Reflect.apply(line,this,[message]);
  };
 }});
const profileKey='first-frame-profile-pending';
let lastPersist=-Infinity;
let carry=null;try{carry=JSON.parse(sessionStorage.getItem(profileKey)||'null');}catch{}
if(carry?.start){
 metrics.launchStartedAt=carry.start-performance.timeOrigin;
 metrics.launchStartedAbsoluteTime=carry.start;
 metrics.maxLaunchHeartbeatGapMs=carry.maxGap;
 metrics.maxPreWarmupHeartbeatGapMs=carry.maxPreGap;
}
let lastTimer=carry?.lastHeartbeat?carry.lastHeartbeat-performance.timeOrigin:performance.now();
let lastGapStart=null,lastTickState=null;
function diagnosticState(){const s=window.blenderStartupStats?.snapshot();return s?{phase:s.phase,operation:s.operation,label:s.label,dependencies:s.dependencies,workersRequested:s.workersRequested,workersReady:s.workersReady,lastNativeMarker:s.lastNativeMarker}:null;}
function accountGap(now){
 if(metrics.launchStartedAt&&!metrics.finishedAt){
  const gap=now-Math.max(lastTimer,metrics.launchStartedAt);
  if(gap>250){
   const record={startMs:Math.max(lastTimer,metrics.launchStartedAt),endMs:now,gapMs:gap,before:lastTickState,after:diagnosticState()};
   if(lastGapStart===lastTimer)metrics.longGaps[metrics.longGaps.length-1]=record;
   else{metrics.longGaps.push(record);if(metrics.longGaps.length>80)metrics.longGaps.shift();lastGapStart=lastTimer;}
  }
  metrics.maxLaunchHeartbeatGapMs=Math.max(metrics.maxLaunchHeartbeatGapMs,gap);
  if(!metrics.warmupStartedAt)metrics.maxPreWarmupHeartbeatGapMs=Math.max(metrics.maxPreWarmupHeartbeatGapMs,gap);
 }
 if(metrics.warmupStartedAt&&!metrics.finishedAt){
  metrics.maxHeartbeatGapMs=Math.max(metrics.maxHeartbeatGapMs,now-Math.max(lastTimer,metrics.warmupStartedAt));
 }
}
function persistLaunch(){
 if(!metrics.launchStartedAbsoluteTime||metrics.finishedAt)return;
 accountGap(performance.now());
 lastPersist=performance.now();
 try{sessionStorage.setItem(profileKey,JSON.stringify({start:metrics.launchStartedAbsoluteTime,
  lastHeartbeat:performance.timeOrigin+lastTimer,maxGap:metrics.maxLaunchHeartbeatGapMs,
  maxPreGap:metrics.maxPreWarmupHeartbeatGapMs}));}catch{}
}
window.addEventListener('pagehide',persistLaunch);
const pipeline=GPUDevice.prototype.createRenderPipeline;
GPUDevice.prototype.createRenderPipeline=function(...args){
  metrics.pipelines++;
  if(metrics.pipelines===4){accountGap(performance.now());metrics.warmupStartedAt=performance.now();}
  const until=performance.now()+metrics.injectedDelayMs;
  while(performance.now()<until){}
  return Reflect.apply(pipeline,this,args);
};
setInterval(()=>{
 const now=performance.now();accountGap(now);lastTimer=now;lastTickState=diagnosticState();
 if(now-lastPersist>=250)persistLaunch();
 if(metrics.warmupStartedAt&&!document.body?.dataset.rendered)metrics.timerTicks++;
},10);
function sample(){
 if(metrics.warmupStartedAt&&!document.body?.dataset.rendered)metrics.rafTicks++;
 if(document.body?.dataset.rendered&&!metrics.finishedAt){
  const now=performance.now();accountGap(now);metrics.finishedAt=now;
  try{sessionStorage.removeItem(profileKey);}catch{}
 }
 requestAnimationFrame(sample);
}requestAnimationFrame(sample);

})();
