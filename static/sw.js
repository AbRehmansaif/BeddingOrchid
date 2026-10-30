// BeddingOrchid PWA Service Worker
const CACHE_NAME = 'beddingorchid-v1';
const PRECACHE_ASSETS = [
  '/',
  '/static/images/favicon.svg',
  '/static/images/pwa/icon-192.png',
  '/static/images/pwa/icon-512.png',
  '/static/images/pwa/icon-maskable-192.png',
  '/static/images/pwa/icon-maskable-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('Precache partial failure:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      )
    )
  );
  self.clients.claim();
});

// Network-first strategy with cache fallback
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  
  // Skip admin and API calls
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/account/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Cache successful responses for static assets
        if (networkResponse && networkResponse.status === 200 && event.request.url.includes('/static/')) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse;
          if (event.request.mode === 'navigate') {
            return caches.match('/');
          }
        });
      })
  );
});
