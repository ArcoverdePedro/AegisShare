const { test, expect } = require('@playwright/test');

const RX_DENIED_CLIENT = {
  username: 'ci-rx-denied-client',
  password: 'ci-rx-denied-client-password',
};

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(RX_DENIED_CLIENT.username);
  await page.getByLabel('Senha').fill(RX_DENIED_CLIENT.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function expectForbidden(page, path) {
  const response = await page.goto(path);
  expect(response, `Navegação para ${path} deve produzir resposta HTTP`).not.toBeNull();
  expect(response.status(), `${path} deve permanecer negado para papel CLI`).toBe(403);
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toHaveCount(0);
}

test('papel CLI permanece negado nas superfícies RX mesmo com permissões mal atribuídas', async ({ page }) => {
  await login(page);

  await expectForbidden(page, '/medicamentos/');
  await expectForbidden(page, '/medicamentos/novo/');
  await expectForbidden(page, '/medicamentos/00000000-0000-0000-0000-000000000001/editar/');
  await expectForbidden(page, '/estoque-farmacia/');
});
