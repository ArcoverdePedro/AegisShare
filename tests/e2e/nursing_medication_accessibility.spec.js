const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const ADMINISTER_URL = '/enfermagem/medicacoes/80000000-0000-4000-8000-000000000004/administrar/';
const VIEWPORTS = [
  { name: 'telefone', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
];

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill('ci-nursing-offline');
  await page.getByLabel('Senha').fill('ci-nursing-offline-password');
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

test('administração permanece acessível em telefone e tablet', async ({ page }) => {
  await page.setViewportSize({ width: VIEWPORTS[0].width, height: VIEWPORTS[0].height });
  await login(page);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto(ADMINISTER_URL);

    await expect(page.getByRole('heading', { name: 'Confirmar administração' })).toBeVisible();
    await expect(page.getByLabel('Momento da administração')).toBeVisible();
    await expect(page.getByLabel('Dose efetivamente administrada')).toBeVisible();
    await expect(page.getByLabel('Unidade da dose administrada')).toBeVisible();
    await expect(
      page.getByLabel(/Confirmo que a dose informada foi efetivamente administrada/)
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Confirmar administração' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Cancelar' })).toBeVisible();

    await expectNoSeriousAxeViolations(page);
    await expectNoPageOverflow(page);
  }
});
