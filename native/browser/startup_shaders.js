// SPDX-License-Identifier: GPL-2.0-or-later
// Reuse translations emitted by this exact native engine. New GLSL variants
// retain Blender's existing compiler and source-keyed native cache. Variants
// translated during a session are kept in IndexedDB for the same engine, so
// later sessions skip the slow main-thread compiler for them as well.
(()=>{
  'use strict';
  const report={version:'startup-shaders-v2',status:'not loaded',entries:0,hits:0,misses:0,
    stored:0,persisted:0,persistence:'unavailable'};
  window.blenderStartupShaderCacheReport=report;
  const KEY=/^v8:[vfc]:[a-f0-9]{16}:\d+$/,MAX_TRANSLATION=262144;
  // Bounded so a long session cannot grow storage or startup memory without limit.
  const MAX_STORED=1500,MAX_STORED_CHARS=24*1048576,STORE='translations',PREFIX='blender-native-shaders-';
  const valid=(key,value)=>typeof key==='string'&&KEY.test(key)&&
    typeof value==='string'&&value.length>=1&&value.length<=MAX_TRANSLATION;
  const request=(operation,timeoutMs=3000)=>new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('Shader storage timed out')),timeoutMs);
    operation.onsuccess=()=>{clearTimeout(timer);resolve(operation.result);};
    operation.onerror=()=>{clearTimeout(timer);reject(operation.error||Error('Shader storage failed'));};
  });
  async function openStore(engineSHA256){
    if(typeof indexedDB==='undefined')throw Error('IndexedDB unavailable');
    const name=PREFIX+engineSHA256.slice(0,16);
    const opening=indexedDB.open(name,1);
    opening.onupgradeneeded=()=>opening.result.createObjectStore(STORE);
    const database=await request(opening);
    // Translations from other engines can never match; drop them without waiting.
    indexedDB.databases?.().then(list=>{
      for(const entry of list)if(entry.name?.startsWith(PREFIX)&&entry.name!==name)indexedDB.deleteDatabase(entry.name);
    }).catch(()=>{});
    return database;
  }
  async function restore(database,cache){
    const transaction=database.transaction(STORE,'readonly'),store=transaction.objectStore(STORE);
    const [keys,values]=await Promise.all([request(store.getAllKeys()),request(store.getAll())]);
    let chars=0,count=0;
    for(let i=0;i<keys.length&&count<MAX_STORED;i++){
      const key=keys[i],value=values[i];
      if(!valid(key,value)||chars+value.length>MAX_STORED_CHARS)continue;
      chars+=value.length;count++;
      if(!cache.has(key))cache.set(key,value);
    }
    return {count,chars};
  }
  function persistNewTranslations(database,cache,used){
    const pending=new Map();let timer=null,{count,chars}=used;
    const flush=()=>new Promise(resolve=>{
      timer=null;
      if(!pending.size){resolve();return;}
      const batch=[...pending];pending.clear();
      try{
        const transaction=database.transaction(STORE,'readwrite'),store=transaction.objectStore(STORE);
        for(const [key,value] of batch)store.put(value,key);
        transaction.oncomplete=()=>{report.persisted+=batch.length;resolve();};
        transaction.onerror=transaction.onabort=()=>{report.persistence='write failed';resolve();};
      }catch(error){report.persistence='write failed';resolve();}
    });
    window.blenderFlushNativeShaderCache=flush;
    globalThis.__WGSL_CACHE_PUT__=(key,value)=>{
      if(report.persistence!=='enabled'||!valid(key,value))return;
      if(count>=MAX_STORED||chars+value.length>MAX_STORED_CHARS){report.persistence='storage limit reached';return;}
      count++;chars+=value.length;pending.set(key,value);
      // Batch writes outside the frame that produced the translation.
      if(timer===null)timer=setTimeout(flush,2000);
    };
    addEventListener('pagehide',()=>{if(pending.size)flush();});
  }
  window.prepareBlenderStartupShaders=async()=>{
    if(window.blenderDisableStartupShaderCache){report.status='disabled for validation';return report;}
    try{
      const [identityResponse,seedResponse]=await Promise.all([
        fetch('engine_identity.json'),fetch('startup_shader_seed.json')]);
      if(!identityResponse.ok||!seedResponse.ok)throw Error('Shader seed or engine identity unavailable');
      const identity=await identityResponse.json(),text=await seedResponse.text();
      if(text.length>2097152)throw Error('Shader seed exceeds size limit');
      const seed=JSON.parse(text);
      if(seed.version!==1||seed.schema!=='v8-fnv64-length'||
          !/^[a-f0-9]{64}$/.test(identity.sha256)||seed.engineSHA256!==identity.sha256){
        report.status='engine mismatch; using native compiler';return report;
      }
      if(!Array.isArray(seed.entries)||seed.entries.length>500)throw Error('Invalid shader seed entries');
      const seen=new Set();
      for(const entry of seed.entries){
        if(!Array.isArray(entry)||entry.length!==2||!valid(entry[0],entry[1])||seen.has(entry[0])){
          throw Error('Invalid native shader translation');
        }
        seen.add(entry[0]);
      }
      class NativeShaderCache extends Map{
        get(key){const value=super.get(key);if(value===undefined)report.misses++;else report.hits++;return value;}
      }
      const cache=new NativeShaderCache(seed.entries);
      globalThis.__WGSL_CACHE__=cache;
      report.status='native translations loaded';report.entries=seed.entries.length;
      report.engineSHA256=identity.sha256;
      try{
        const database=await openStore(identity.sha256);
        const used=await restore(database,cache);
        report.stored=used.count;report.persistence='enabled';
        persistNewTranslations(database,cache,used);
      }catch(error){report.persistence='unavailable: '+String(error).slice(0,120);}
    }catch(error){report.status='seed unavailable; using native compiler';report.error=String(error).slice(0,180);}
    return report;
  };
})();
