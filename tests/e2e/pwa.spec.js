const { test, expect } = require('@playwright/test');

const SENSITIVE_CACHE_PREFIXES = [
  '/pacientes/',
  '/encontros/',
  '/evolucoes/',
  '/arquivos/',
  '/aegis-admin/',
  '/api/',
];

test('registers the PWA shell and serves only the generic offline fallback', async ({ page, context }) => {
  await page.goto('/');

  const manifest = page.locator('link[rel="manifest"]');
  await expect(manifest).toHaveAttribute('href', '/manifest.webmanifest');

  await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) throw new Error('Service Worker indisponível');
    await navigator.serviceWorker.ready;
  });

  await expect.poll(async () => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);

  await context.setOffline(true);
  await page.goto('/sobre/?pwa-offline-ci=1');
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  await expect(page.getByText('Nenhum dado clínico identificável')).toBeVisible();
  await context.setOffline(false);

  const cachedPaths = await page.evaluate(async () => {
    const paths = [];
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        paths.push(new URL(request.url).pathname);
      }
    }
    return paths;
  });

  for (const prefix of SENSITIVE_CACHE_PREFIXES) {
    expect(cachedPaths.some((path) => path.startsWith(prefix)), `${prefix} não pode estar no cache`).toBe(false);
  }
});

test('manifest exposes installable standalone metadata and both required icons', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.ok()).toBe(true);

  const manifest = await response.json();
  expect(manifest.name).toBe('AegisShare HIS');
  expect(manifest.short_name).toBe('AegisShare');
  expect(manifest.start_url).toBe('/');
  expect(manifest.scope).toBe('/');
  expect(manifest.display).toBe('standalone');
  expect(manifest.orientation).toBe('portrait');
  expect(manifest.icons.map((icon) => icon.sizes)).toEqual(['192x192', '512x512']);

  for (const icon of manifest.icons) {
    const iconResponse = await request.get(icon.src);
    expect(iconResponse.ok()).toBe(true);
    expect(iconResponse.headers()['content-type']).toContain('image/png');
  }
});
