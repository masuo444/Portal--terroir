const CACHE_NAME = 'thub-quest-v1';
const URLS = ['/sake/quest/', '/sake/search_index.json'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(URLS))));
self.addEventListener('fetch', e => e.respondWith(fetch(e.request).catch(() => caches.match(e.request))));
