// SPDX-License-Identifier: GPL-2.0-or-later
const PREFIX = `blender-port:${new URL('./', self.location).pathname}:`;
const CACHE = PREFIX + 'math-v1';
const ASSETS = ['./', './index.html', './style.css', './app.mjs', './math-runtime.mjs',
  './manifest.webmanifest', './icon.svg', './icon-192.png', './icon-512.png', './COPYING.txt',
  './engine/blender-math.wasm', './engine/build.json', './engine/source.tar.gz'];
const urls = ASSETS.map(path => new URL(path, self.location).href);

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    try { await cache.addAll(urls); }
    catch (error) { await caches.delete(CACHE); throw error; }
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(PREFIX) && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || !urls.includes(event.request.url)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    return (await cache.match(event.request)) || fetch(event.request);
  })());
});
self.addEventListener('message', event => {
  if (event.data !== 'check-offline' || !event.ports[0]) return;
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const complete = (await Promise.all(urls.map(url => cache.match(url)))).every(Boolean);
    event.ports[0].postMessage({ complete });
  })());
});
