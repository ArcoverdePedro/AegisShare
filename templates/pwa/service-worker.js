const CACHE_VERSION = 'aegisshare-shell-v2';
const OFFLINE_URL = '{% url "pwa:offline" %}';
const OFFLINE_DATABASES = ['aegisshare-offline'];
const PRECACHE_URLS = [
    OFFLINE_URL,
    '{% url "pwa:manifest" %}',
    '{% url "pwa:icon" 192 %}',
    '{% url "pwa:icon" 512 %}',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys
                    .filter((key) => key.startsWith('aegisshare-') && key !== CACHE_VERSION)
                    .map((key) => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    // Navegações nunca são persistidas. Se a rede cair, devolvemos apenas o
    // fallback genérico, sem conteúdo autenticado ou clínico em cache.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request, { cache: 'no-store' })
                .catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }

    // Somente assets estáticos podem ser armazenados dinamicamente. Todo o restante
    // do monólito (PEP, arquivos, administração e formulários) permanece network-only.
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then((cached) => {
                if (cached) return cached;
                return fetch(request).then((response) => {
                    if (response.ok && response.type === 'basic') {
                        const clone = response.clone();
                        caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
                    }
                    return response;
                });
            })
        );
        return;
    }

    event.respondWith(fetch(request, { cache: 'no-store' }));
});

function deleteIndexedDb(name) {
    return new Promise((resolve) => {
        const request = indexedDB.deleteDatabase(name);
        request.onsuccess = resolve;
        request.onerror = resolve;
        request.onblocked = resolve;
    });
}

self.addEventListener('message', (event) => {
    if (!event.data || event.data.type !== 'CLEAR_LOCAL_DATA') return;

    event.waitUntil(
        Promise.all([
            caches.keys().then((keys) => Promise.all(
                keys
                    .filter((key) => key.startsWith('aegisshare-'))
                    .map((key) => caches.delete(key))
            )),
            ...OFFLINE_DATABASES.map(deleteIndexedDb),
        ])
    );
});
