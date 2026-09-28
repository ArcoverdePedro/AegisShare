const {test, expect} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const LIST='/rh/funcionarios/';
const DETAIL='/rh/funcionarios/10000000-0000-4000-8000-000000000010/';
const ADD='/aegis-admin/hr/employee/add/';
const CHANGE='/aegis-admin/hr/employee/10000000-0000-4000-8000-000000000010/change/';

async function localRows(page) {
  return page.evaluate(async () => {
    const counts={};
    for(const info of await indexedDB.databases()) {
      const db=await new Promise((resolve,reject)=>{const request=indexedDB.open(info.name);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
      for(const store of db.objectStoreNames) counts[`${info.name}/${store}`]=await new Promise((resolve,reject)=>{const request=db.transaction(store).objectStore(store).count();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
      db.close();
    }
    return counts;
  });
}
async function login(page, role='operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-hr-${role}`);
  await page.getByLabel('Senha').fill(`ci-hr-${role}-password`);
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await expect(page).toHaveURL(/\/$/);
}
test('CA-HR-01/02/03: criar, editar e preservar usuário',async ({page})=>{
  await login(page);
  await page.goto(ADD);
  await page.locator('#id_user').selectOption('10000000-0000-4000-8000-000000000006');
  await page.locator('#id_department').fill('Suprimentos sintético HR');
  await page.locator('#id_job_title').fill('Analista sintético HR');
  await page.locator('input[name=_save]').click();
  await expect(page).toHaveURL(/\/aegis-admin\/hr\/employee\/$/);
  await page.goto(CHANGE);
  await expect(page.getByText('ci-hr-operator',{exact:true})).toBeVisible();
  await expect(page.locator('select[name=user]')).toHaveCount(0);
  await page.locator('#id_department').fill('Setor alterado HR');
  await page.locator('#id_active').uncheck();
  await page.locator('input[name=_save]').click();
  await page.goto(DETAIL);
  await expect(page.getByText('Usuário: ci-hr-operator',{exact:true})).toBeVisible();
  await expect(page.getByText('Setor: Setor alterado HR',{exact:true})).toBeVisible();
  await expect(page.getByText('Cadastro: inativo',{exact:true})).toBeVisible();
});
test('CA-HR-04: consulta institucional exige capacidade e papel interno',async ({page})=>{
  await login(page,'viewer');
  expect((await page.goto(LIST)).status()).toBe(200);
  await expect(page.getByText('ci-hr-operator',{exact:false})).toBeVisible();
  await page.goto(ADD);
  await expect(page).toHaveURL(/\/login\/\?next=/);
  await login(page,'client');
  expect((await page.goto(LIST)).status()).toBe(403);
  expect((await page.goto(DETAIL)).status()).toBe(403);
});
test('CA-HR-07: offline não persiste página ou formulário',async ({page,context})=>{
  await login(page);
  await page.evaluate(()=>navigator.serviceWorker.ready);
  await page.goto(CHANGE);
  await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true);
  const before=await localRows(page);
  await context.setOffline(true);
  await page.goto(LIST);
  await expect(page.getByRole('heading',{name:'Você está sem conexão'})).toBeVisible();
  await context.setOffline(false);
  await page.goto(LIST);
  expect(await localRows(page)).toEqual(before);
  const evidence=await page.evaluate(async ()=>{
    const urls=[];let sensitive=false;
    for(const name of await caches.keys()) for(const request of await (await caches.open(name)).keys()) {
      urls.push(request.url);const response=await (await caches.open(name)).match(request);
      if(/text|json|javascript/.test(response.headers.get('content-type')||'')) sensitive ||= (await response.text()).includes('Setor sintético HR');
    }
    sensitive ||= JSON.stringify(localStorage).includes('Setor sintético HR')||JSON.stringify(sessionStorage).includes('Setor sintético HR');
    return {urls,sensitive};
  });
  expect(evidence.sensitive).toBe(false);
  expect(evidence.urls.some(url=>url.includes('/rh/funcionarios/')||url.includes('/aegis-admin/hr/employee/'))).toBe(false);
});
test('CA-HR-07: telefone/tablet sem overflow e axe',async ({page})=>{
  test.setTimeout(90000);
  await login(page);
  for(const viewport of [{width:390,height:844},{width:768,height:1024}]) {
    await page.setViewportSize(viewport);
    for(const url of [LIST,DETAIL,ADD,CHANGE]) {
      await page.goto(url);
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(result.violations.filter(v=>['serious','critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width+1);
    }
  }
});
test('CA-HR-02/04: revogar change no Admin com formulário aberto',async ({page,browser})=>{
  await login(page,'delegate');
  await page.goto(CHANGE);
  await page.locator('#id_department').fill('Mudança não autorizada');
  const adminContext=await browser.newContext({baseURL:process.env.PWA_BASE_URL});
  try {
    const adminPage=await adminContext.newPage();await login(adminPage,'admin');
    await adminPage.goto('/aegis-admin/aegis_share/customuser/10000000-0000-4000-8000-000000000003/change/');
    const permission=adminPage.locator('#id_user_permissions_to option').filter({hasText:/Can change employee/i});
    const value=await permission.getAttribute('value');
    await adminPage.locator('#id_user_permissions_to').selectOption(value);
    await adminPage.locator('#id_user_permissions_remove, #id_user_permissions_remove_link').click();
    await adminPage.locator('input[name=_save]').click();
    await expect(adminPage).toHaveURL(/customuser\/$/);
    const posted=page.waitForResponse(r=>r.url().endsWith(CHANGE)&&r.request().method()==='POST');
    await page.locator('input[name=_save]').click();
    expect((await posted).status()).toBe(403);
    expect((await page.goto(DETAIL)).status()).toBe(200);
    await expect(page.getByText('Mudança não autorizada')).toHaveCount(0);
  } finally {await adminContext.close();}
});
