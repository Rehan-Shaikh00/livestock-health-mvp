/* Offline shell cache: cache-first for built assets, network-first for navigation. POSTs never intercepted. */
const CACHE = 'pashu-arogya-v1';
self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || req.url.includes('/api/v1/events')) return;
  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(req).then(res => { const c = res.clone(); caches.open(CACHE).then(x => x.put(req, c)).catch(() => {}); return res; }).catch(() => caches.match(req)));
    return;
  }
  e.respondWith(fetch(req).then(res => { const c = res.clone(); caches.open(CACHE).then(x => x.put(req, c)).catch(() => {}); return res; })
    .catch(() => caches.match(req).then(hit => hit || caches.match('/index.html'))));
});
