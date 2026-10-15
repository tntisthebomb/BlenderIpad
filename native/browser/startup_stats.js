// SPDX-License-Identifier: GPL-2.0-or-later
// Small startup breadcrumbs, independent of Blender's WASM runtime.
(()=>{
  'use strict';
  const key='blender-startup-stats-last';
  let began=performance.now();
  const state={version:'startup-stats-v4',active:false,phase:'Waiting to start',phaseSeconds:0,
    elapsedSeconds:0,operation:'None yet',operationStatus:'not started',label:'',wasmMemoryBytes:null,dependencies:null,
    wasmMode:'not started',wasmMimeType:null,mainInstanceReady:false,workersRequested:0,workersReady:0,
    shaderModules:0,renderPipelines:0,computePipelines:0,texturesCreated:0,buffersCreated:0,
    bufferBytesRequested:0,canvasBacking:null,canvasCss:null,lines:[],updatedAt:null};
  let previous=null,memory=null,lastSaved=0,lastOutputUpdate=-Infinity,compact=false;
  try{previous=JSON.parse(localStorage.getItem(key)||'null');}catch{}
  const panel=document.createElement('aside');panel.id='startup-stats';
  panel.setAttribute('aria-label','Blender startup statistics');
  panel.innerHTML='<button id="toggle-startup-stats" type="button">Hide details</button><strong id="startup-stats-title"></strong><pre id="startup-stats-text"></pre>';
  document.body.append(panel);
  const title=panel.querySelector('strong'),text=panel.querySelector('pre'),toggle=panel.querySelector('button');
  function snapshot(){
    return {...state,lines:state.lines.slice(),error:state.error};
  }
  function update(save=false,force=false){
    state.elapsedSeconds=Math.round((performance.now()-began)/1000);
    try{state.wasmMemoryBytes=memory?.buffer.byteLength ?? window.blenderEditor?.getBlenderMemoryBytes?.() ?? state.wasmMemoryBytes;}catch{}
    const canvas=document.getElementById('canvas');
    if(canvas){state.canvasBacking=[canvas.width,canvas.height];state.canvasCss=[canvas.clientWidth,canvas.clientHeight];}
    const view=!state.active&&previous ? previous : state;
    title.textContent=!state.active&&previous ? 'Previous startup — Blender is stopped' : 'Blender startup · diagnostic stats v4';
    const mib=value=>(value/1048576).toFixed(1)+' MiB';
    text.textContent=[
      'Step: '+view.phase,
      'Elapsed: '+view.elapsedSeconds+' s · in step: '+Math.max(0,view.elapsedSeconds-view.phaseSeconds)+' s',
      'Last operation: '+view.operation+(view.label?' · '+view.label:'')+' · '+(view.operationStatus??'completion not recorded'),
      'WASM memory: '+(view.wasmMemoryBytes===null?'not available yet':mib(view.wasmMemoryBytes))+' · total iPad RAM use unavailable',
      'WASM loader: '+(view.wasmMode??'not recorded')+' · MIME: '+(view.wasmMimeType??'not recorded'),
      'Main WASM instance: '+(view.mainInstanceReady?'ready':'not ready')+' · native workers: '+(view.workersReady??0)+' / '+(view.workersRequested??0)+' ready',
      'Canvas: '+(view.canvasBacking?.join(' × ')??'not recorded')+' pixels · CSS: '+(view.canvasCss?.join(' × ')??'not recorded'),
      'Dependencies left: '+(view.dependencies??'not reported'),
      'Creation requests: '+view.shaderModules+' shaders · '+view.renderPipelines+' render pipelines · '+view.computePipelines+' compute pipelines',
      'GPU resource requests: '+view.texturesCreated+' textures · '+view.buffersCreated+' buffers',
      'GPU buffer requests: '+mib(view.bufferBytesRequested)+' cumulative (not live usage)',
      ...(view.error?['Error: '+view.error]:[]),
      ...view.lines.map(line=>'> '+line)
    ].join('\n');
    if(window.blenderDeviceReport)window.blenderDeviceReport.startupStats=snapshot();
    if(save&&state.active&&(force||performance.now()-lastSaved>=1000)){
      state.updatedAt=new Date().toISOString();lastSaved=performance.now();
      try{localStorage.setItem(key,JSON.stringify(snapshot()));}catch{}
    }
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
  function instrumentDevice(device){
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
          return value;
        } catch(error) {
          if(tracked){state.operationStatus='call threw';update(true,true);}
          throw error;
        }
      };
    }
  }
  window.blenderStartupStats={snapshot,instrumentDevice,
    previousAttempt(){return previous;},
    phase(phase){
      state.phase=phase;state.phaseSeconds=Math.round((performance.now()-began)/1000);update(true,true);
    },
    start(){began=performance.now();state.phaseSeconds=0;state.active=true;previous=null;operation('Starting Blender');},
    // Thousands of files can change the dependency count synchronously. Keep
    // only the count; the heartbeat paints it, with a final immediate update.
    dependencies(count){state.dependencies=count;if(count===0)update(true,true);},
    line(message){
      const line=String(message).replace(/\s+/g,' ').trim();
      if(line){state.lines.push(line.slice(0,180));state.lines=state.lines.slice(-4);}
      if(performance.now()-lastOutputUpdate>=250){lastOutputUpdate=performance.now();update(true);}
    },
    failure(message){
      const value=String(message),at=value.lastIndexOf(' - error ');
      const useful=at>=0?value.slice(at+9):value;
      state.error=useful.slice(0,600);operation('Stopped after error',state.label);
    }
  };
  toggle.onclick=()=>{
    compact=!compact;text.hidden=compact;toggle.textContent=compact?'Show details':'Hide details';
  };
  addEventListener('pagehide',()=>update(true,true));
  document.addEventListener('visibilitychange',()=>update(true,true));
  setInterval(()=>{if(!document.hidden)update(true);},1000);
  update();
})();
