const CACHE_PREFIX=`blender-ipad:${self.registration.scope}:`;
const CACHE=`${CACHE_PREFIX}__BUILD_CACHE__`;
const FILES=['./','index.html','editor.html','blender-core.js','blender-core.wasm','blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','editor_files.js','editor_input.js','ipad-startup.html'];
self.addEventListener('message',event=>{
  if (event.data?.type==='BUILD_INFO') event.ports[0]?.postMessage({cache:CACHE});
});
self.addEventListener('install',event=>event.waitUntil((async()=>{
  try {
    const cache=await caches.open(CACHE);
    for (const path of FILES) await cache.add(new Request(new URL(path,self.location),{cache:'reload'}));
    // An update must wait until the old application's tabs are closed. Claiming
    // an active runtime here could mix its JS with the next build's WASM/data.
    if (!self.registration.active) await self.skipWaiting();
  } catch(error) {
    await caches.delete(CACHE);
    throw error;
  }
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
  for (const key of await caches.keys()) {
    if (key.startsWith(CACHE_PREFIX) && key!==CACHE) await caches.delete(key);
  }
  await self.clients.claim();
})()));
self.addEventListener('fetch',event=>{
  const request=event.request;
  if (request.method!=='GET' || new URL(request.url).origin!==self.location.origin) return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    const cached=await cache.match(request,{ignoreSearch:true});
    const response=cached || await fetch(request);
    if (!response.ok || response.type==='opaque') return response;
    const headers=new Headers(response.headers);
    headers.set('Cross-Origin-Opener-Policy','same-origin');
    headers.set('Cross-Origin-Embedder-Policy','require-corp');
    headers.set('Cross-Origin-Resource-Policy','same-origin');
    headers.delete('Content-Encoding');
    headers.delete('Content-Length');
    return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
  })());
});
