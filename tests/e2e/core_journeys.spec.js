const { test, expect } = require('@playwright/test');

const ADMIN = {
  username: 'ci-e2e-admin',
  password: 'ci-e2e-admin-password',
};
const RECIPIENT = {
  username: 'ci-e2e-recipient',
  password: 'ci-e2e-recipient-password',
};
const FILE_NAME = 'ci-e2e-document.txt';
const PUBLIC_LINK_PASSWORD = 'ci-public-link-pass';

async function login(page, credentials) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(credentials.username);
  await page.getByLabel('Senha').fill(credentials.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('button', { name: new RegExp(credentials.username) })).toBeVisible();
}

test('login rejeita credenciais invalidas e aceita o administrador E2E', async ({ page }) => {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill('ci-e2e-invalid');
  await page.getByLabel('Senha').fill('senha-incorreta');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL(/\/login\/$/);
  await expect(
    page.locator('#message-container').getByText('Usuario ou senha invalidos.', { exact: true })
  ).toBeVisible();

  await login(page, ADMIN);
  await expect(page.getByRole('link', { name: /Arquivos/ })).toBeVisible();
});

test('administrador localiza e abre documento acessivel', async ({ page }) => {
  await login(page, ADMIN);
  await page.goto('/arquivos/');

  const row = page.locator('tr').filter({ hasText: FILE_NAME });
  await expect(row).toBeVisible();
  await expect(row).toContainText('ci-e2e-owner');
  await row.getByRole('link', { name: 'Abrir' }).click();

  await expect(page.getByRole('heading', { name: FILE_NAME })).toBeVisible();
  await expect(page.getByText('Seguranca e integridade')).toBeVisible();
  await expect(page.getByText('Arquivo legado', { exact: true })).toBeVisible();
});

test('compartilhamento direto e link publico protegido preservam autorizacao', async ({ page, browser }) => {
  await login(page, ADMIN);
  await page.goto('/arquivos/');

  const row = page.locator('tr').filter({ hasText: FILE_NAME });
  await row.getByRole('link', { name: 'Abrir' }).click();

  const shareBox = page.locator('.box').filter({ hasText: 'Compartilhar com usuario' });
  await expect(shareBox).toBeVisible();
  const recipientOption = shareBox.locator('option').filter({ hasText: RECIPIENT.username }).first();
  if (await recipientOption.count()) {
    const recipientValue = await recipientOption.getAttribute('value');
    expect(recipientValue).toBeTruthy();
    await shareBox.locator('select[name="usuario_id"]').selectOption(recipientValue);
    await shareBox.getByRole('button', { name: 'Conceder acesso' }).click();
  }
  await expect(shareBox).toContainText(RECIPIENT.username);

  const linkBox = page.locator('.box').filter({ hasText: 'Link temporario' });
  await linkBox.locator('select[name="expires_in_hours"]').selectOption('1');
  await linkBox.locator('input[name="password"]').fill(PUBLIC_LINK_PASSWORD);
  await linkBox.locator('input[name="allow_download"]').uncheck();
  await linkBox.getByRole('button', { name: 'Criar link seguro' }).click();

  const generatedLink = page.locator('#newSharedLink');
  await expect(generatedLink).toBeVisible();
  const publicUrl = await generatedLink.inputValue();
  expect(publicUrl).toContain('/s/');

  const publicContext = await browser.newContext();
  const publicPage = await publicContext.newPage();
  await publicPage.goto(publicUrl);
  await expect(publicPage.getByText('Este arquivo e protegido por senha.')).toBeVisible();
  await publicPage.locator('input[name="password"]').fill(PUBLIC_LINK_PASSWORD);
  await publicPage.getByRole('button', { name: 'Continuar' }).click();
  await expect(publicPage.getByRole('heading', { name: 'Compartilhamento seguro' })).toBeVisible();
  await expect(publicPage.getByText(FILE_NAME)).toBeVisible();
  await expect(publicPage.getByRole('link', { name: 'Visualizar' })).toBeVisible();
  await expect(publicPage.getByRole('link', { name: 'Baixar' })).toHaveCount(0);
  await publicContext.close();

  const recipientContext = await browser.newContext();
  const recipientPage = await recipientContext.newPage();
  await login(recipientPage, RECIPIENT);
  await recipientPage.goto('/arquivos/');
  const sharedRow = recipientPage.locator('tr').filter({ hasText: FILE_NAME });
  await expect(sharedRow).toBeVisible();
  await sharedRow.getByRole('link', { name: 'Abrir' }).click();
  await expect(recipientPage.getByRole('heading', { name: FILE_NAME })).toBeVisible();
  await recipientContext.close();
});
