const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const LIST = '/interop/laboratorio/';
const CREATE = `${LIST}receber/`;
const SOURCE = '12000000-0000-4000-8000-000000000001';
const MARKER = 'INBOX-PLAINTEXT-SYNTHETIC';
async function login(page, role = 'operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-inbox-${role}`);
  await page.getByLabel('Senha').fill(`ci-inbox-${role}-password`);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}
async function fill(page) {
  await page.getByLabel('Origem', { exact: true }).selectOption(SOURCE);
  await page.getByLabel('Arquivo para quarentena').setInputFiles({name: 'never-retained.txt', mimeType: 'text/plain', buffer: Buffer.from(MARKER)});
  await page.getByLabel('Confirmo o depósito').check();
}
async function receive(page) {
  await page.goto(CREATE);
  await fill(page);
  await page.getByRole('button', {name: 'Receber em quarentena'}).click();
  await expect(page.getByRole('heading', {name: 'Recibo laboratorial', exact: true})).toBeVisible();
  return page.url();
}
test('CA-INBOX: recebimento, retry e isolamento por origem', async ({page}) => {
  await login(page);
  const detail = await receive(page);
  expect(await receive(page)).toBe(detail);
  await expect(page.getByText(MARKER)).toHaveCount(0);
  await expect(page.getByText('never-retained.txt')).toHaveCount(0);
  await login(page, 'outsider');
  expect((await page.goto(detail)).status()).toBe(404);
  await page.goto(LIST);
  await expect(page.getByText('INBOX-SYNTH', {exact: true})).toHaveCount(0);
});
test('CA-INBOX: telefone e tablet com axe', async ({page}) => {
  test.setTimeout(90000);
  await login(page);
  const detail = await receive(page);
  for (const viewport of [{width:390,height:844}, {width:768,height:1024}]) {
    await page.setViewportSize(viewport);
    for (const url of [LIST, CREATE, detail]) {
      await page.goto(url);
      const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(result.violations.filter(v => ['serious','critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width + 1);
    }
  }
});
test('CA-INBOX: offline não guarda arquivo nem página privada', async ({page,context}) => {
  await login(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.goto(CREATE);
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await fill(page);
  const before = await page.evaluate(async () => {
    const rows = {};
    for (const info of await indexedDB.databases()) {
      const db = await new Promise(resolve => { const req = indexedDB.open(info.name); req.onsuccess = () => resolve(req.result); });
      for (const store of db.objectStoreNames) rows[`${info.name}/${store}`] = await new Promise(resolve => {const req=db.transaction(store).objectStore(store).count();req.onsuccess=()=>resolve(req.result);});
      db.close();
    }
    return rows;
  });
  await context.setOffline(true);
  await Promise.all([page.waitForEvent('framenavigated', frame=>frame===page.mainFrame()), page.getByRole('button',{name:'Receber em quarentena'}).click()]);
  await page.goto(LIST);
  await expect(page.getByRole('heading',{name:'Você está sem conexão'})).toBeVisible();
  await context.setOffline(false);
  await page.goto(LIST);
  const evidence = await page.evaluate(async marker => {
    const rows = {}, urls = []; let sensitive = false;
    for (const info of await indexedDB.databases()) {
      const db=await new Promise(resolve=>{const req=indexedDB.open(info.name);req.onsuccess=()=>resolve(req.result);});
      for (const store of db.objectStoreNames) rows[`${info.name}/${store}`]=await new Promise(resolve=>{const req=db.transaction(store).objectStore(store).count();req.onsuccess=()=>resolve(req.result);});
      db.close();
    }
    for(const name of await caches.keys()) for(const request of await (await caches.open(name)).keys()) {
      urls.push(request.url);
      const response=await (await caches.open(name)).match(request);
      if(/text|json|javascript/.test(response.headers.get('content-type')||'')) sensitive ||= (await response.text()).includes(marker);
    }
    sensitive ||= JSON.stringify(localStorage).includes(marker) || JSON.stringify(sessionStorage).includes(marker);
    return {rows,urls,sensitive};
  }, MARKER);
  expect(evidence.rows).toEqual(before);
  expect(evidence.sensitive).toBe(false);
  expect(evidence.urls.some(url=>url.includes(LIST))).toBe(false);
});
