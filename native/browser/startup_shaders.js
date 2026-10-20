// SPDX-License-Identifier: GPL-2.0-or-later
// Reuse translations emitted by this exact native engine. New GLSL variants
// retain Blender's existing compiler and source-keyed native cache.
(()=>{
  'use strict';
  const report={version:'startup-shaders-v1',status:'not loaded',entries:0,hits:0,misses:0};
  window.blenderStartupShaderCacheReport=report;
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
        if(!Array.isArray(entry)||entry.length!==2||typeof entry[0]!=='string'||
            !/^v8:[vfc]:[a-f0-9]{16}:\d+$/.test(entry[0])||seen.has(entry[0])||
            typeof entry[1]!=='string'||entry[1].length<1||entry[1].length>262144){
          throw Error('Invalid native shader translation');
        }
        seen.add(entry[0]);
      }
      class NativeShaderCache extends Map{
        get(key){const value=super.get(key);if(value===undefined)report.misses++;else report.hits++;return value;}
      }
      globalThis.__WGSL_CACHE__=new NativeShaderCache(seed.entries);
      report.status='native translations loaded';report.entries=seed.entries.length;
      report.engineSHA256=identity.sha256;
    }catch(error){report.status='seed unavailable; using native compiler';report.error=String(error).slice(0,180);}
    return report;
  };
})();
