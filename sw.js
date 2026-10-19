// PWA Service Worker for Offline Caching
const CACHE_NAME = "tw50-intern-v2";
const ASSETS_TO_CACHE = [
  "./",
  "./index.html",
  "./app.js",
  "./data/data.json",
  "./data/target_companies.json",
  "./data/course_vocabulary.json",
  "./manifest.json"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  // Network first with cache fallback to guarantee fresh updates
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp && resp.status === 200 && resp.type === "basic") {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
