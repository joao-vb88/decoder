// Nome e versão do cache — mude a versão pra forçar atualização
const CACHE_NAME = 'decoder-v1';

// Arquivos que ficam em cache (shell do app)
const SHELL = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// Instala: pré-cacheia o shell
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL))
  );
});

// Ativa: limpa caches antigos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch: estratégia "network-first" para POST e "cache-first" para GET do shell
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Não cacheia POST (o /decode é POST) nem requisições externas
  if (request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // Para a página e assets do shell: cache-first, cai pra rede
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((resp) => {
          // Guarda cópia no cache (só se for OK)
          if (resp && resp.status === 200 && resp.type === 'basic') {
            const clone = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return resp;
        })
        .catch(() => caches.match('/')); // fallback offline
    })
  );
});