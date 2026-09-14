const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const RX_ADMIN = {
  username: 'ci-rx-accessibility',
  password: 'ci-rx-accessibility-password',
};

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(RX_ADMIN.username);
  await page.getByLabel('Senha').fill(RX_ADMIN.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function expectNoSeriousAxeViolations(page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious'
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

async function expectNoPageOverflow(page) {
  const sizes = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.viewportWidth + 1);
}

async function verifyCatalog(page) {
  await page.goto('/medicamentos/');
  await expect(page.getByRole('heading', { name: 'Catálogo de medicamentos' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Novo medicamento' })).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyStock(page) {
  await page.goto('/estoque-farmacia/');
  await expect(page.getByRole('heading', { name: 'Estoque farmacêutico' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();
  await expect(page.getByText('E2E-RX-A11Y-001')).toBeVisible();
  await expectNoPageOverflow(page);
}

test('catálogo e estoque RX não apresentam violações sérias WCAG nas superfícies existentes', async ({ page }) => {
  await login(page);

  await page.goto('/medicamentos/');
  await expectNoSeriousAxeViolations(page);

  await page.goto('/estoque-farmacia/');
  await expectNoSeriousAxeViolations(page);
});

test('catálogo e estoque RX preservam layout essencial em telefone e tablet', async ({ page }) => {
  await login(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await verifyCatalog(page);
  await expectNoSeriousAxeViolations(page);
  await verifyStock(page);
  await expectNoSeriousAxeViolations(page);

  await page.setViewportSize({ width: 768, height: 1024 });
  await verifyCatalog(page);
  await expectNoSeriousAxeViolations(page);
  await verifyStock(page);
  await expectNoSeriousAxeViolations(page);
});
