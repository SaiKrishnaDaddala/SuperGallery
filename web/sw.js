// Never cache NAS files or authenticated API responses. Offline navigation gets
// an honest reconnect screen rather than an incomplete, stale application shell.
const SHELL = 'sg-shell-v3';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/static/offline.html'])).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith('sg-shell-') && k !== SHELL).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin || e.request.method !== 'GET' || e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(async () => (await caches.match('/static/offline.html')) || new Response('Your NAS is offline. Reconnect and reload.', {status:503, headers:{'Content-Type':'text/plain'}})));
});
