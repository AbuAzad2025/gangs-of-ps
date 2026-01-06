const CACHE_NAME = 'gangs-palestine-v1';
const ASSETS_TO_CACHE = [
  '/static/img/azad_logo_white_on_dark.png',
  '/static/css/custom.css',
  '/static/manifest.json'
];

// Install Event
self.addEventListener('install', (evt) => {
  console.log('[ServiceWorker] Install');
  evt.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Pre-caching offline page');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', (evt) => {
  console.log('[ServiceWorker] Activate');
  evt.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(keyList.map((key) => {
        if (key !== CACHE_NAME) {
          console.log('[ServiceWorker] Removing old cache', key);
          return caches.delete(key);
        }
      }));
    })
  );
  self.clients.claim();
});

// Fetch Event
self.addEventListener('fetch', (evt) => {
  // Only handle GET requests
  if (evt.request.method !== 'GET') return;

  evt.respondWith(
    fetch(evt.request)
      .catch(() => {
        return caches.match(evt.request);
      })
  );
});