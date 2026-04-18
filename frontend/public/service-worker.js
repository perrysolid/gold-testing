// NFR-4: Offline-first PWA service worker
// TODO: replace with workbox-generated SW for production
const CACHE_NAME = "aurum-v1";
const STATIC = ["/", "/index.html", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(STATIC)));
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((cached) => cached ?? fetch(e.request))
  );
});
