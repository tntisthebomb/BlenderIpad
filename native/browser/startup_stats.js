// SPDX-License-Identifier: GPL-2.0-or-later
// Small startup breadcrumbs, independent of Blender's WASM runtime.
(()=>{
  'use strict';
  const key='blender-startup-stats-last';
  let began=performance.now();
  const state={version:'startup-stats-v7',attemptId:null,progressSequence:0,startedAt:null,pageVisible:!document.hidden,traceUnavailable:[],watchdogStatus:'not started',watchdogMaxGapMs:0,recentOperations:[],active:false,phase:'Waiting to start',phaseSeconds:0,
    elapsedSeconds:0,operation:'None yet',operationStatus:'not started',label:'',wasmMemoryBytes:null,dependencies:null,
    wasmMode:'not started',wasmMimeType:null,mainInstanceReady:false,workersRequested:0,workersReady:0,
    shaderModules:0,renderPipelines:0,computePipelines:0,texturesCreated:0,buffersCreated:0,
    commandEncoders:0,renderPasses:0,computePasses:0,drawCalls:0,queueSubmissions:0,nativeQueueSubmissions:0,nativeBridgeEvents:0,nativeInitStages:[],lastNativeMarker:null,firstSubmission:'not submitted',
    bufferBytesRequested:0,canvasBacking:null,canvasCss:null,lines:[],updatedAt:null};
  let previous=null,previousWatchdog=null,watchdog=null,sharedRecorder=null,sharedState=null,recorderReady=Promise.resolve(),resolveRecorder=null,lastEventSignature=null,memory=null,lastSaved=0,lastOutputUpdate=-Infinity,lastPaint=-Infinity,compact=false;
  try{previous=JSON.parse(localStorage.getItem(key)||'null');}catch{}
  const panel=document.createElement('aside');panel.id='startup-stats';
  panel.setAttribute('aria-label','Blender startup statistics');
  panel.innerHTML='<button id="toggle-startup-stats" type="button">Hide details</button><strong id="startup-stats-title"></strong><pre id="startup-stats-text"></pre>';
  document.body.append(panel);
  const title=panel.querySelector('strong'),text=panel.querySelector('pre'),toggle=panel.querySelector('button');
  function snapshot(){
    return {...state,lines:state.lines.slice(),recentOperations:state.recentOperations.slice(),nativeInitStages:state.nativeInitStages.slice(),error:state.error};
  }
  function previousSnapshot(){
    const recovery=previousWatchdog?.checkpoint&&(!previous||
      (previous.attemptId&&previousWatchdog.attemptId===previous.attemptId))?previousWatchdog.checkpoint:null;
    return recovery&&(!previous||(recovery.progressSequence??0)>=(previous.progressSequence??0))?recovery:previous;
  }
  function update(save=false,force=false,durable=false){
    const now=performance.now(),paint=!state.active||durable||now-lastPaint>=250;
    state.elapsedSeconds=Math.round((performance.now()-began)/1000);
    try{state.wasmMemoryBytes=memory?.buffer.byteLength ?? window.blenderEditor?.getBlenderMemoryBytes?.() ?? state.wasmMemoryBytes;}catch{}
    // Layout reads and text replacement are presentation work, not checkpoints.
    if(paint){const canvas=document.getElementById('canvas');
      if(canvas){state.canvasBacking=[canvas.width,canvas.height];state.canvasCss=[canvas.clientWidth,canvas.clientHeight];}}
    if(force&&state.active){
      state.progressSequence++;
      const signature=[state.operation,state.label,state.operationStatus].join('|');
      if(signature!==lastEventSignature){
        state.recentOperations.push({seconds:((performance.now()-began)/1000).toFixed(2),
          operation:state.operation,label:state.label,status:state.operationStatus});
        state.recentOperations=state.recentOperations.slice(-32);lastEventSignature=signature;
      }
    }
    if(save&&state.active){
      // The reserved-file recorder receives every API boundary, even inside a
      // long synchronous native call. localStorage is only the fallback: forcing
      // it for every draw/upload can repeatedly block the browser storage path.
      state.updatedAt=new Date().toISOString();
      if(durable||now-lastSaved>=1000||(force&&state.watchdogStatus!=='recording')){
        lastSaved=now;
        try{localStorage.setItem(key,JSON.stringify(snapshot()));}catch{}
      }
      try{sendWatchdog({kind:'checkpoint',checkpoint:snapshot()});}catch{}
    }
    if(!paint)return;
    lastPaint=now;
    const previousView=previousSnapshot();
    const view=!state.active&&previousView ? previousView : state;
    const hasRecovery=!!previousWatchdog&&view.attemptId!=null&&previousWatchdog.attemptId===view.attemptId;
    title.textContent=!state.active&&previousView ? 'Previous startup — Blender is stopped' : 'Blender startup · diagnostic stats v7';
    const mib=value=>(value/1048576).toFixed(1)+' MiB';
    text.textContent=[
      'Step: '+view.phase,
      'Elapsed: '+view.elapsedSeconds+' s · in step: '+Math.max(0,view.elapsedSeconds-view.phaseSeconds)+' s',
      'Last operation: '+view.operation+(view.label?' · '+view.label:'')+' · '+(view.operationStatus??'completion not recorded'),
      'Latest native marker: '+(view.lastNativeMarker?view.lastNativeMarker.seconds+' s · '+view.lastNativeMarker.text:'not recorded'),
      'WASM memory: '+(view.wasmMemoryBytes===null?'not available yet':mib(view.wasmMemoryBytes))+' · total iPad RAM use unavailable',
      'WASM loader: '+(view.wasmMode??'not recorded')+' · MIME: '+(view.wasmMimeType??'not recorded'),
      'Main WASM instance: '+(view.mainInstanceReady?'ready':'not ready')+' · native workers: '+(view.workersReady??0)+' / '+(view.workersRequested??0)+' ready',
      'Canvas: '+(view.canvasBacking?.join(' × ')??'not recorded')+' pixels · CSS: '+(view.canvasCss?.join(' × ')??'not recorded'),
      'Dependencies left: '+(view.dependencies??'not reported'),
      'Creation requests: '+view.shaderModules+' shaders · '+view.renderPipelines+' render pipelines · '+view.computePipelines+' compute pipelines',
      'Startup command calls: '+(view.commandEncoders??0)+' encoders · '+(view.renderPasses??0)+' render passes · '+(view.computePasses??0)+' compute passes · '+(view.drawCalls??0)+' draws',
      'Queue: '+(view.queueSubmissions??0)+' browser submits · '+(view.nativeQueueSubmissions??'not recorded')+' traced native entries (96-event cap) · first completion: '+(view.firstSubmission??'not recorded'),
      'Recovery recorder: '+(state.active?view.watchdogStatus:(hasRecovery?'saved':'not recorded'))+' · longest main heartbeat gap: '+Math.round((hasRecovery?previousWatchdog.maxHeartbeatGapMs:view.watchdogMaxGapMs??0)/1000)+' s'+(hasRecovery?' · observed at '+previousWatchdog.observedElapsedSeconds+' s':''),
      ...(view.traceUnavailable?.length?['Trace unavailable: '+view.traceUnavailable.join(', ')]:[]),
      'GPU resource requests: '+view.texturesCreated+' textures · '+view.buffersCreated+' buffers',
      'GPU buffer requests: '+mib(view.bufferBytesRequested)+' cumulative (not live usage)',
      ...(view.error?['Error: '+view.error]:[]),
      ...view.lines.map(line=>'> '+line)
    ].join('\n');
    if(window.blenderDeviceReport){window.blenderDeviceReport.startupStats=snapshot();if(!state.active&&previousView)window.blenderDeviceReport.previousStartupStats=previousView;}
  }
  function operation(name,label='',status='in progress'){
    state.operationStatus=status;state.operation=name;state.label=String(label||'').slice(0,160);update(true,true);
  }
  function findMemory(imports){
    if(imports?.env?.memory instanceof WebAssembly.Memory)memory=imports.env.memory;
  }
  // Preserve the original API results and errors. Recording the operation
  // before the call leaves a breadcrumb even if compilation never returns.
  for(const name of ['instantiateStreaming','instantiate']){
    const original=WebAssembly[name];if(typeof original!=='function')continue;
    WebAssembly[name]=function(...args){
      state.wasmMode=name==='instantiateStreaming'?'streaming':(args[0] instanceof WebAssembly.Module?'compiled module':'buffered');
      if(name==='instantiateStreaming'){
        Promise.resolve(args[0]).then(response=>{
          state.wasmMimeType=response?.headers?.get?.('Content-Type')??null;update(true,true);
        },()=>{});
      }
      findMemory(args[1]);operation('Compiling / instantiating WebAssembly');
      const result=Reflect.apply(original,this,args);
      // Observe completion without replacing the Promise returned to Emscripten.
      Promise.resolve(result).then(()=>{
        state.mainInstanceReady=true;operation('Main WebAssembly instance ready','','completed');
      },()=>{});
      return result;
    };
  }
  // Emscripten sends the compiled module to each native worker before starting
  // Blender. Keep its handlers, transfer list, receiver and return untouched.
  const trackedWorkers=new WeakSet(),post=globalThis.Worker?.prototype.postMessage;
  if(post)Worker.prototype.postMessage=function(message,...rest){
    if(message?.cmd==='load'&&!trackedWorkers.has(this)){
      trackedWorkers.add(this);state.workersRequested++;
      this.addEventListener('message',event=>{
        if(event.data?.cmd==='loaded'){
          state.workersReady++;operation('Native worker ready',state.workersReady+' / '+state.workersRequested,'completed');
        }
      });
      operation('Preparing native worker',state.workersRequested);
    }
    return Reflect.apply(post,this,[message,...rest]);
  };
  const pipelines=new WeakMap(),instrumented=new WeakSet();
  let watchedSubmission=false;
  function trace(target,method,label,counter,after,describe){
    const original=target?.[method];if(typeof original!=='function')return;
    const wrapper=function(...args){
      if(counter&&state.phase!=='Viewport presented')state[counter]++;
      // Trace startup boundaries. The steady editor keeps inexpensive counts
      // without synchronous DOM/storage work for each draw.
      const recording=state.active&&state.phase!=='Viewport presented';
      if(recording)operation(label,describe?.(args)??'');
      try {
        const result=Reflect.apply(original,this,args);
        if(recording){state.operationStatus='call returned';update(true,true);}
        try{after?.(result,args);}catch{unavailable(method);}
        return result;
      } catch(error) {
        if(recording){state.operationStatus='call threw';update(true,true);}
        throw error;
      }
    };
    try{target[method]=wrapper;if(target[method]!==wrapper)unavailable(method);}
    catch{unavailable(method);}
  }
  function unavailable(method){
    if(!state.traceUnavailable.includes(method))state.traceUnavailable=state.traceUnavailable.concat(method).slice(-8);
  }
  function instrumentPass(pass,label){
    if(state.phase==='Viewport presented'||!pass||instrumented.has(pass))return;
    instrumented.add(pass);let pipeline='';
    trace(pass,'setPipeline','Setting pass pipeline',null,(_,args)=>{
      pipeline=pipelines.get(args[0])??'';
    },args=>pipelines.get(args[0])??label);
    for(const method of ['draw','drawIndexed','drawIndirect','drawIndexedIndirect']){
      trace(pass,method,'Encoding '+method,'drawCalls',null,()=>label+(pipeline?' · '+pipeline:''));
    }
    for(const method of ['dispatchWorkgroups','dispatchWorkgroupsIndirect','end']){
      trace(pass,method,'Encoding '+method,null,null,()=>label);
    }
  }
  function instrumentEncoder(encoder){
    if(state.phase==='Viewport presented'||!encoder||instrumented.has(encoder))return;
    instrumented.add(encoder);
    trace(encoder,'beginRenderPass','Beginning render pass','renderPasses',
      (pass,args)=>instrumentPass(pass,args[0]?.label??''),args=>args[0]?.label??'');
    trace(encoder,'beginComputePass','Beginning compute pass','computePasses',
      (pass,args)=>instrumentPass(pass,args[0]?.label??''),args=>args[0]?.label??'');
    trace(encoder,'finish','Finishing command encoder');
  }
  function instrumentQueue(queue){
    if(!queue||instrumented.has(queue))return;instrumented.add(queue);
    trace(queue,'submit','Submitting GPU commands','queueSubmissions',()=>{
      if(watchedSubmission||typeof queue.onSubmittedWorkDone!=='function')return;
      watchedSubmission=true;state.firstSubmission='waiting for callback';
      try {
        queue.onSubmittedWorkDone().then(()=>{
          state.firstSubmission='completed';update(true,true);
        },error=>{state.firstSubmission='rejected: '+String(error).slice(0,120);update(true,true);});
      } catch(error){state.firstSubmission='observer failed: '+String(error).slice(0,100);}
    });
    for(const method of ['writeBuffer','writeTexture'])trace(queue,method,'GPU queue '+method);
  }
  function instrumentCanvas(context){
    if(!context||instrumented.has(context))return;instrumented.add(context);
    for(const method of ['configure','getCurrentTexture','unconfigure']){
      trace(context,method,'GPU canvas '+method);
    }
  }
  function instrumentDevice(device){
    if(instrumented.has(device))return;instrumented.add(device);
    for(const method of ['createBindGroupLayout','createPipelineLayout','createBindGroup']){
      trace(device,method,'GPU '+method,null,null,args=>args[0]?.label??'');
    }
    trace(device,'createCommandEncoder','Creating command encoder','commandEncoders',instrumentEncoder);
    instrumentQueue(device.queue);
    for(const [method,counter,label] of [
      ['createShaderModule','shaderModules','Creating shader module'],
      ['createRenderPipeline','renderPipelines','Compiling render pipeline'],
      ['createComputePipeline','computePipelines','Compiling compute pipeline'],
      ['createTexture','texturesCreated','Creating texture'],
      ['createBuffer','buffersCreated','Creating buffer']]){
      const original=device[method];if(typeof original!=='function')continue;
      device[method]=function(descriptor,...rest){
        state[counter]++;
        if(method==='createBuffer')state.bufferBytesRequested+=Number(descriptor?.size)||0;
        if(['createShaderModule','createRenderPipeline','createComputePipeline'].includes(method))operation(label,descriptor?.label);
        const tracked=['createShaderModule','createRenderPipeline','createComputePipeline'].includes(method);
        try {
          const value=Reflect.apply(original,this,[descriptor,...rest]);
          if(tracked){state.operationStatus='call returned';update(true,true);}
          if(method==='createRenderPipeline'||method==='createComputePipeline'){
            if(value&&typeof value==='object')pipelines.set(value,String(descriptor?.label??''));
            trace(value,'getBindGroupLayout','Getting pipeline bind-group layout',null,null,()=>descriptor?.label??'');
          }
          return value;
        } catch(error) {
          if(tracked){state.operationStatus='call threw';update(true,true);}
          throw error;
        }
      };
    }
  }
  function sendWatchdog(message){
    if(!sharedRecorder||!sharedState)return;
    if(message.kind==='checkpoint')sharedState.checkpoint=message.checkpoint;
    else if(message.kind==='heartbeat')sharedState.lastHeartbeat=Date.now();
    else if(message.kind==='visibility'){sharedState.visible=message.visible;sharedState.lastHeartbeat=Date.now();}
    else if(message.kind==='native-line'){
      sharedState.checkpoint={...sharedState.checkpoint,lines:(sharedState.checkpoint.lines??[]).concat(message.line).slice(-4),
        progressSequence:message.progressSequence,elapsedSeconds:message.elapsedSeconds,lastNativeMarker:message.lastNativeMarker};
    } else if(message.kind==='stop'){sharedState.checkpoint=message.checkpoint;sharedState.stopped=true;}
    try {
      const bytes=new TextEncoder().encode(JSON.stringify(sharedState));
      const header=new Int32Array(sharedRecorder,0,4),payload=new Uint8Array(sharedRecorder,16);
      if(bytes.length>payload.length)throw Error('Recovery checkpoint exceeds shared capacity');
      Atomics.add(header,0,1);payload.set(bytes);Atomics.store(header,1,bytes.length);Atomics.add(header,0,1);
      if(sharedState.stopped){Atomics.store(header,2,1);Atomics.notify(header,2);}
    } catch(error){state.watchdogStatus='shared recorder unavailable: '+String(error).slice(0,100);}
  }
  function startWatchdog(){
    if(!globalThis.Worker||!globalThis.SharedArrayBuffer||!navigator.storage?.getDirectory){state.watchdogStatus='unavailable';return;}
    try {
      const attemptId=state.attemptId;
      recorderReady=new Promise(resolve=>{resolveRecorder=resolve;setTimeout(()=>{if(state.attemptId===attemptId&&state.watchdogStatus==='starting'){state.watchdogStatus='initialization timed out';update(true,true);}resolve();},10000);});
      sharedRecorder=new SharedArrayBuffer(131088);
      sharedState={checkpoint:snapshot(),lastHeartbeat:Date.now(),visible:!document.hidden,stopped:false};
      sendWatchdog({kind:'checkpoint',checkpoint:snapshot()});
      watchdog=new Worker(new URL('startup_watchdog.js',document.baseURI),{name:'blender-startup-watchdog'});
      state.watchdogStatus='starting';
      watchdog.onmessage=event=>{
        const message=event.data;
        if(message.kind==='storage-error'){state.watchdogStatus='storage unavailable: '+message.message.slice(0,100);resolveRecorder?.();}
        else if(message.kind==='ready'){state.watchdogStatus='recording';resolveRecorder?.();}
        else if(message.kind==='sample')state.watchdogMaxGapMs=message.maxHeartbeatGapMs;
        else if(message.kind==='stopped'){watchdog=null;sharedRecorder=null;sharedState=null;if(!state.watchdogStatus.startsWith('storage unavailable'))state.watchdogStatus='finished';}
        update();
      };
      watchdog.onerror=event=>{event.preventDefault();state.traceUnavailable.push('Recovery worker: '+String(event.message||'worker failed').slice(0,160));resolveRecorder?.();state.watchdogStatus='unavailable';watchdog?.terminate();watchdog=null;sharedRecorder=null;sharedState=null;update();};
      watchdog.postMessage({kind:'start',attemptId:state.attemptId,shared:sharedRecorder});
    } catch {state.watchdogStatus='unavailable';watchdog=null;sharedRecorder=null;sharedState=null;resolveRecorder?.();}
  }
  function checksum(text){let value=2166136261;for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619)>>>0;return value.toString(16);}
  async function readPreviousWatchdog(){
    try {
      const root=await navigator.storage.getDirectory();
      const reports=await Promise.all(['blender-startup-recovery-a.json','blender-startup-recovery-b.json'].map(async name=>{
        try {
          const handle=await root.getFileHandle(name),file=await handle.getFile();
          const envelope=JSON.parse(await file.text());
          if(envelope.version!==2||typeof envelope.payload!=='string'||checksum(envelope.payload)!==envelope.checksum)return null;
          const record=JSON.parse(envelope.payload);
          return typeof record.observedAt==='number'&&record.checkpoint?record:null;
        } catch {return null;}
      }));
      previousWatchdog=reports.filter(Boolean).sort((a,b)=>b.observedAt-a.observedAt)[0]??null;
      if(window.blenderDeviceReport)window.blenderDeviceReport.previousWatchdogReport=previousWatchdog;
      update();
    } catch {}
  }
  window.blenderStartupStats={snapshot,instrumentDevice,instrumentQueue,instrumentCanvas,
    nativeBridge(stage,status,detail){
      if(!state.active||state.phase==='Viewport presented')return;
      state.nativeBridgeEvents++;if(stage==='queue-submit-enter')state.nativeQueueSubmissions++;
      state.lastNativeMarker={seconds:((performance.now()-began)/1000).toFixed(2),text:(stage+' '+detail).slice(0,180)};
      operation('Native bridge',stage+(detail?' · '+detail:''),status);
    },
    previousRecovery(){return previousWatchdog;},
    recoveryReady(){return recorderReady;},
    previousAttempt(){return previousSnapshot();},
    phase(phase){
      state.phase=phase;state.phaseSeconds=Math.round((performance.now()-began)/1000);update(true,true,true);
      if(phase==='Viewport presented')sendWatchdog({kind:'stop',checkpoint:snapshot()});
    },
    start(){began=performance.now();state.phaseSeconds=0;state.active=true;previous=null;state.startedAt=Date.now();state.attemptId=state.startedAt+'-'+Math.random().toString(36).slice(2,8);startWatchdog();operation('Starting Blender');},
    // Thousands of files can change the dependency count synchronously. Keep
    // only the count; the heartbeat paints it, with a final immediate update.
    dependencies(count){state.dependencies=count;if(count===0)update(true,true,true);},
    line(message){
      const line=String(message).replace(/\s+/g,' ').trim();
      if(line){
        const bounded=line.slice(0,180);state.lines.push(bounded);state.lines=state.lines.slice(-4);
        state.lastNativeMarker={text:bounded,seconds:((performance.now()-began)/1000).toFixed(2)};
        if(state.active&&state.phase!=='Viewport presented'){
          state.progressSequence++;
          try{sendWatchdog({kind:'native-line',line:bounded,progressSequence:state.progressSequence,
            elapsedSeconds:Math.round((performance.now()-began)/1000),lastNativeMarker:state.lastNativeMarker});}catch{}
        }
      }
      if(state.active&&state.phase!=='Viewport presented'&&line.startsWith('GPU initialization: ')){
        const stage=line.slice('GPU initialization: '.length);
        state.nativeInitStages.push(stage);state.nativeInitStages=state.nativeInitStages.slice(-16);
        operation('Native GPU initialization',stage,stage==='complete'?'completed':'in progress');
      }
      if(performance.now()-lastOutputUpdate>=250){lastOutputUpdate=performance.now();update(true);}
    },
    failure(message){
      const value=String(message),at=value.lastIndexOf(' - error ');
      const useful=at>=0?value.slice(at+9):value;
      state.error=useful.slice(0,600);operation('Stopped after error',state.label);update(true,true,true);
    }
  };
  toggle.onclick=()=>{
    compact=!compact;text.hidden=compact;toggle.textContent=compact?'Show details':'Hide details';
  };
  addEventListener('pagehide',()=>update(true,true,true));
  document.addEventListener('visibilitychange',()=>{state.pageVisible=!document.hidden;try{sendWatchdog({kind:'visibility',visible:state.pageVisible});}catch{}update(true,true,true);});
  setInterval(()=>{if(!document.hidden){update(true);if(state.active)try{sendWatchdog({kind:'heartbeat'});}catch{}}},1000);
  update();readPreviousWatchdog();
})();
