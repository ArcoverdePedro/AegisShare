const {test, expect} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const CREATE='/estoque/requisicoes/nova/';
const LIST='/estoque/requisicoes/';
const MATERIAL='09000000-0000-4000-8000-000000000002';
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

async function login(page, role='operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-inventory-${role}`);
  await page.getByLabel('Senha').fill(`ci-inventory-${role}-password`);
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page).toHaveURL(/\/$/);
}
async function fill(page, material=MATERIAL) {
  await page.getByLabel('Material não medicamentoso').selectOption(material);
  await page.getByLabel('Quantidade inteira').fill('3');
  await page.getByLabel('Confirmo a requisição interna').check();
}
async function detail(page) {
  await page.goto(CREATE);
  await fill(page);
  await page.getByRole('button',{name:'Registrar requisição',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Requisição de material',exact:true})).toBeVisible();
  return page.url();
}
test('CA-INV-01/03/04: registrar, alterar catálogo, retry e snapshots',async ({page,browser})=>{
  await login(page);
  await page.goto(CREATE);
  await fill(page,MATERIAL.replace('000000000002','000000000001'));
  const payload=await page.locator('form.box').evaluate(form=>Object.fromEntries(new FormData(form)));
  await page.getByRole('button',{name:'Registrar requisição',exact:true}).click();
  const url=page.url();
  await expect(page.getByText('Quantidade: 3 caixa',{exact:true})).toBeVisible();
  const adminContext=await browser.newContext({baseURL:process.env.PWA_BASE_URL});
  try {
    const adminPage=await adminContext.newPage();
    await login(adminPage,'admin');
    await adminPage.goto('/aegis-admin/inventory/inventoryitem/09000000-0000-4000-8000-000000000001/change/');
    await adminPage.getByLabel('Nome:',{exact:true}).fill('Nome alterado INV');
    await adminPage.getByLabel('Unidade de contagem:',{exact:true}).fill('unidade');
    await adminPage.getByLabel('Ativo',{exact:true}).uncheck();
    await adminPage.locator('input[name=_save]').click();
    await expect(adminPage).toHaveURL(/inventoryitem\/$/);
    const retry=await page.request.post(CREATE,{form:payload});
    expect(retry.status()).toBe(200);
    expect(retry.url()).toBe(url);
    await page.goto(url);
    await expect(page.getByText('Material: INV-E2E-1 · Material sintético INV 1',{exact:true})).toBeVisible();
    await expect(page.getByText('Quantidade: 3 caixa',{exact:true})).toBeVisible();
    await page.goto('/estoque/');
    await expect(page.getByText('Nome alterado INV')).toHaveCount(0);
  } finally { await adminContext.close(); }
});
test('CA-INV-02: consulta institucional, leitor e cliente',async ({page})=>{
  await login(page);
  const url=await detail(page);
  await login(page,'reader');
  expect((await page.goto(url)).status()).toBe(200);
  await expect(page.getByText('ci-inventory-operator',{exact:false})).toBeVisible();
  expect((await page.goto(CREATE)).status()).toBe(403);
  await login(page,'client');
  expect((await page.goto(url)).status()).toBe(403);
  expect((await page.goto('/estoque/')).status()).toBe(403);
});
test('CA-INV-07: offline sem cache ou fila',async ({page,context})=>{
  await login(page);
  await page.goto(CREATE);
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true);
  await fill(page);
  const before=await localRows(page);
  await context.setOffline(true);
  await Promise.all([page.waitForEvent('framenavigated',frame=>frame===page.mainFrame()),page.getByRole('button',{name:'Registrar requisição',exact:true}).click()]);
  await page.goto('/estoque/');
  await expect(page.getByRole('heading',{name:'Você está sem conexão'})).toBeVisible();
  await context.setOffline(false);
  await page.goto(LIST);
  expect(await localRows(page)).toEqual(before);
  const urls=await page.evaluate(async ()=>{
    const urls=[];
    for(const name of await caches.keys()) for(const request of await (await caches.open(name)).keys()) {
      urls.push(request.url);
      const response=await (await caches.open(name)).match(request);
      if(/text|json|javascript/.test(response.headers.get('content-type')||'')) {
        if((await response.text()).includes('Material sintético INV')) throw new Error('Texto privado em cache');
      }
    }
    if(JSON.stringify(localStorage).includes('Material sintético INV')||JSON.stringify(sessionStorage).includes('Material sintético INV')) throw new Error('Texto privado em storage');
    return urls;
  });
  expect(urls.some(url=>url.includes('/estoque/'))).toBe(false);
});
test('CA-INV-07: telefone/tablet sem overflow e axe',async ({page})=>{
  test.setTimeout(90000);
  await login(page);
  const url=await detail(page);
  for(const viewport of [{width:390,height:844},{width:768,height:1024}]) {
    await page.setViewportSize(viewport);
    for(const target of ['/estoque/',LIST,CREATE,url]) {
      await page.goto(target);
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(result.violations.filter(v=>['serious','critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width+1);
    }
  }
});
test('CA-INV-02: revogar capacidade no Admin com formulário aberto',async ({page,browser})=>{
  await login(page,'delegate');
  await page.goto(CREATE);
  await fill(page);
  const adminContext=await browser.newContext({baseURL:process.env.PWA_BASE_URL});
  try {
    const adminPage=await adminContext.newPage();
    await login(adminPage,'admin');
    await adminPage.goto('/aegis-admin/aegis_share/customuser/09000000-0000-4000-8000-000000000003/change/');
    const permission=adminPage.locator('#id_user_permissions_to option').filter({hasText:'Pode requisitar material'});
    const value=await permission.getAttribute('value');
    await adminPage.locator('#id_user_permissions_to').selectOption(value);
    await adminPage.locator('#id_user_permissions_remove, #id_user_permissions_remove_link').click();
    await adminPage.locator('input[name=_save]').click();
    await expect(adminPage).toHaveURL(/customuser\/$/);
    const posted=page.waitForResponse(r=>r.url().endsWith(CREATE)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Registrar requisição',exact:true}).click();
    expect((await posted).status()).toBe(403);
    expect((await page.goto(LIST)).status()).toBe(200);
  } finally { await adminContext.close(); }
});
