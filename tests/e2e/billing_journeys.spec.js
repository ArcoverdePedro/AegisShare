const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
test.use({ timezoneId: 'America/Fortaleza' });
const LIST = '/faturamento/contas/';
const OPEN = '/faturamento/encontros/08000000-0000-4000-8000-000000000002/conta/abrir/';

async function localRows(page) {
  return page.evaluate(async () => {
    const counts = {};
    for (const info of await indexedDB.databases()) {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open(info.name);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      for (const store of db.objectStoreNames) {
        counts[`${info.name}/${store}`] = await new Promise((resolve, reject) => {
          const request = db.transaction(store).objectStore(store).count();
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });
      }
      db.close();
    }
    return counts;
  });
}

async function login(page, role = 'operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-billing-${role}`);
  await page.getByLabel('Senha').fill(`ci-billing-${role}-password`);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}
async function account(page) {
  await page.goto(OPEN);
  if (await page.getByRole('heading',{name:'Abrir conta em preparação',exact:true}).count()) {
    await page.getByLabel('Confirmo a abertura').check();
    await page.getByRole('button',{name:'Abrir conta em preparação',exact:true}).click();
  }
  await expect(page.getByRole('heading',{name:'Conta em preparação',exact:true})).toBeVisible();
  return page.url();
}
async function fillItem(page, quantity='3', price='0.10') {
  await page.getByLabel('Descrição administrativa').fill('ITEM-BILL-SYNTHETIC');
  await page.getByLabel('Quantidade inteira').fill(quantity);
  await page.getByLabel('Valor unitário (BRL)').fill(price);
  await page.getByLabel('Confirme os dados manuais').check();
}
test('CA-BILL-01/03/04: abertura, item, total e retry', async ({page}) => {
  await login(page);
  await page.goto(OPEN);
  await page.getByLabel('Confirmo a abertura').check();
  const opening = await page.locator('form.box').evaluate(form=>Object.fromEntries(new FormData(form)));
  await page.getByRole('button',{name:'Abrir conta em preparação',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Conta em preparação',exact:true})).toBeVisible();
  const detail = page.url();
  const retry = await page.request.post(OPEN,{form:opening});
  expect(retry.status()).toBe(200);
  expect(retry.url()).toBe(detail);
  await page.getByRole('link',{name:'Adicionar item',exact:true}).click();
  await fillItem(page);
  const itemUrl = page.url();
  const data = await page.locator('form.box').evaluate(form=>Object.fromEntries(new FormData(form)));
  await page.getByRole('button',{name:'Registrar item',exact:true}).click();
  await expect(page).toHaveURL(detail);
  expect((await page.request.post(itemUrl,{form:data})).status()).toBe(200);
  await page.getByRole('link',{name:'Adicionar item',exact:true}).click();
  await fillItem(page,'1','0.20');
  await page.getByRole('button',{name:'Registrar item',exact:true}).click();
  await expect(page.getByText('Total em preparação (BRL): 0,50',{exact:true})).toBeVisible();
});
test('CA-BILL-02: capacidade não revela outro escopo PEP', async ({page}) => {
  await login(page);
  const detail = await account(page);
  await login(page,'outsider');
  expect((await page.goto(detail)).status()).toBe(404);
  expect((await page.goto(OPEN)).status()).toBe(404);
  expect((await page.goto(detail+'itens/novo/')).status()).toBe(404);
  await page.goto(LIST);
  await expect(page.getByText('Pessoa Sintética BILL')).toHaveCount(0);
});
test('CA-BILL-07: offline não confirma nem armazena item', async ({page,context}) => {
  await login(page);
  const detail = await account(page);
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await page.goto(detail+'itens/novo/');
  await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true);
  await fillItem(page);
  const rows = await localRows(page);
  await context.setOffline(true);
  await Promise.all([page.waitForEvent('framenavigated',frame=>frame===page.mainFrame()), page.getByRole('button',{name:'Registrar item',exact:true}).click()]);
  await page.goto(LIST);
  await expect(page.getByRole('heading',{name:'Você está sem conexão'})).toBeVisible();
  await context.setOffline(false);
  await page.goto(LIST);
  expect(await localRows(page)).toEqual(rows);
  const evidence = await page.evaluate(async () => {
    const urls=[]; let sensitive=false;
    const markers=['Pessoa Sintética BILL','ITEM-BILL-SYNTHETIC'];
    for(const name of await caches.keys()) for(const request of await (await caches.open(name)).keys()) {
      urls.push(request.url);
      const response=await (await caches.open(name)).match(request);
      if(/text|json|javascript/.test(response.headers.get('content-type')||'')) {
        const body=await response.text(); sensitive ||= markers.some(marker=>body.includes(marker));
      }
    }
    sensitive ||= markers.some(marker=>JSON.stringify(localStorage).includes(marker)||JSON.stringify(sessionStorage).includes(marker));
    return {urls,sensitive};
  });
  expect(evidence.sensitive).toBe(false);
  expect(evidence.urls.some(url=>url.includes('/faturamento/'))).toBe(false);
});
test('CA-BILL-07: telefone e tablet com axe', async ({page}) => {
  test.setTimeout(90000);
  await login(page);
  const detail = await account(page);
  const opening = OPEN.replace('000000000002','000000000005');
  for(const viewport of [{width:390,height:844},{width:768,height:1024}]) {
    await page.setViewportSize(viewport);
    for(const url of [LIST,detail,detail+'itens/novo/',opening]) {
      await page.goto(url);
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(result.violations.filter(v=>['serious','critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width+1);
    }
  }
});
test('CA-BILL-02: revogação real com formulário de item aberto', async ({page,browser}) => {
  await login(page,'delegate');
  const detail = await account(page);
  await page.goto(detail+'itens/novo/');
  await fillItem(page);
  const adminContext=await browser.newContext({baseURL:process.env.PWA_BASE_URL||'http://127.0.0.1:8000'});
  try {
    const adminPage=await adminContext.newPage();
    await login(adminPage,'admin');
    await adminPage.goto('/aegis-admin/pep/patientaccessgrant/08000000-0000-4000-8000-000000000004/delete/');
    await adminPage.locator('input[type=submit]').click();
    await expect(adminPage).toHaveURL(new URL('/aegis-admin/pep/patientaccessgrant/', process.env.PWA_BASE_URL||'http://127.0.0.1:8000').href);
    const posted=page.waitForResponse(response=>response.url()===detail+'itens/novo/' && response.request().method()==='POST');
    await page.getByRole('button',{name:'Registrar item',exact:true}).click();
    expect((await posted).status()).toBe(404);
    expect((await page.goto(detail)).status()).toBe(404);
    await page.goto(LIST);
    await expect(page.getByText('Pessoa Sintética BILL')).toHaveCount(0);
  } finally { await adminContext.close(); }
});
