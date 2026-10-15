const CACHE_NAME = 'vitalguard-shell-v1';
const APP_SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/vitalguard-192.svg', '/icons/vitalguard-512.svg'];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put('/index.html', response.clone()));
      return response;
    }).catch(() => caches.match('/index.html').then((cached) => cached || caches.match('/'))));
    return;
  }
  if (request.destination === 'script' || request.destination === 'style' || request.destination === 'image' || request.destination === 'font') {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
      return response;
    })));
  }
});
self.addEventListener('push', (event) => {
  let payload = { title: 'VitalGuard AI alert', body: 'A new safety signal needs review.', url: '/#/alerts' };
  try { if (event.data) payload = { ...payload, ...event.data.json() }; } catch { if (event.data) payload.body = event.data.text(); }
  event.waitUntil(self.registration.showNotification(payload.title || 'VitalGuard AI alert', {
    body: payload.body || 'A new safety signal needs review.',
    icon: '/icons/vitalguard-192.svg',
    badge: '/icons/vitalguard-192.svg',
    tag: payload.tag || 'vitalguard-alert',
    data: { url: payload.url || '/#/alerts' },
    renotify: true,
  }));
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/#/alerts', self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
    const existing = clients.find((client) => client.url.startsWith(self.location.origin));
    if (existing) { existing.navigate(target); return existing.focus(); }
    return self.clients.openWindow(target);
  }));
});
