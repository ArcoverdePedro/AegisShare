const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const OPERATOR = {
  username: 'ci-adt-operator',
  password: 'ci-adt-operator-password',
};
const OUTSIDER = {
  username: 'ci-adt-outsider',
  password: 'ci-adt-outsider-password',
};
const MASKED_VIEWER = {
  username: 'ci-adt-masked-viewer',
  password: 'ci-adt-masked-viewer-password',
};

async function login(page, credentials) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(credentials.username);
  await page.getByLabel('Senha').fill(credentials.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function selectOptionContaining(page, label, text) {
  const select = page.getByLabel(label);
  const option = select.locator('option').filter({ hasText: text }).first();
  const value = await option.getAttribute('value');
  expect(value, `Opção contendo "${text}" deve existir em ${label}`).toBeTruthy();
  await select.selectOption(value);
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

test('profissional autorizado admite, transfere e dá alta sem perder consistência do mapa', async ({
  page,
}, testInfo) => {
  const retry = Math.min(testInfo.retry, 1);
  const patientName = `Paciente ADT Jornada R${retry}`;
  const sourceLabel = `E2E Jornada R${retry} A`;
  const destinationLabel = `E2E Jornada R${retry} B`;
  const sourceCode = `E2E-J${retry}-A`;
  const destinationCode = `E2E-J${retry}-B`;

  await login(page, OPERATOR);
  await page.goto('/leitos/');
  await expect(page.getByRole('heading', { name: 'Mapa de leitos' })).toBeVisible();

  await page.getByRole('link', { name: 'Nova admissão' }).click();
  await expect(page.getByRole('heading', { name: 'Nova admissão' })).toBeVisible();
  await selectOptionContaining(page, 'Encontro de internação', patientName);
  await selectOptionContaining(page, 'Leito disponível', sourceCode);
  await page.getByRole('button', { name: 'Confirmar admissão' }).click();

  await expect(page).toHaveURL(/\/leitos\/$/);
  await expect(page.getByText('Admissão registrada com sucesso.')).toBeVisible();
  await expect(
    page.getByRole('article', { name: `Leito ${sourceLabel}: OCCUPIED` })
  ).toBeVisible();
  await expect(page.getByText(patientName)).toBeVisible();

  await page.getByRole('link', { name: 'Transferir' }).click();
  await expect(page.getByRole('heading', { name: 'Transferir internação' })).toBeVisible();
  await selectOptionContaining(page, 'Internação ativa', patientName);
  await selectOptionContaining(page, 'Leito de destino', destinationCode);
  await page.getByLabel('Motivo').fill('Transferência sintética E2E.');
  await page.getByRole('button', { name: 'Confirmar transferência' }).click();

  await expect(page).toHaveURL(/\/leitos\/$/);
  await expect(page.getByText('Transferência registrada com sucesso.')).toBeVisible();
  await expect(
    page.getByRole('article', { name: `Leito ${sourceLabel}: AVAILABLE` })
  ).toBeVisible();
  await expect(
    page.getByRole('article', { name: `Leito ${destinationLabel}: OCCUPIED` })
  ).toBeVisible();

  await page.getByRole('link', { name: 'Registrar alta' }).click();
  await expect(page.getByRole('heading', { name: 'Registrar alta' })).toBeVisible();
  await selectOptionContaining(page, 'Internação ativa', patientName);
  await page.getByLabel('Destino da alta').selectOption('HOME');
  await page.getByLabel('Observação da alta').fill('Alta sintética E2E.');
  await page.getByRole('button', { name: 'Confirmar alta' }).click();

  await expect(page).toHaveURL(/\/leitos\/$/);
  await expect(page.getByText('Alta registrada com sucesso.')).toBeVisible();
  await expect(
    page.getByRole('article', { name: `Leito ${destinationLabel}: AVAILABLE` })
  ).toBeVisible();
  await expect(page.getByText(patientName)).toHaveCount(0);
});

test('usuário sem capacidade ADT é negado sem receber o mapa', async ({ page }) => {
  await login(page, OUTSIDER);
  const response = await page.goto('/leitos/');
  expect(response.status()).toBe(403);
  expect(await response.text()).not.toContain('Paciente ADT Sigiloso E2E');
});

test('mapa expõe ocupação operacional sem PHI quando falta escopo PEP', async ({ page }) => {
  await login(page, MASKED_VIEWER);
  await page.goto('/leitos/');

  await expect(page.getByRole('heading', { name: 'Mapa de leitos' })).toBeVisible();
  await expect(
    page.getByRole('article', { name: 'Leito E2E Leito Sigiloso: OCCUPIED' })
  ).toBeVisible();
  await expect(
    page.getByText('Identificação do ocupante restrita ao escopo clínico autorizado.')
  ).toBeVisible();
  await expect(page.getByText('Paciente ADT Sigiloso E2E')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('E2E-ADT-MASKED-PATIENT');
});

test('mapa e formulários ADT mantêm WCAG 2.1 AA essencial em telefone e tablet', async ({ page }) => {
  await login(page, OPERATOR);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/leitos/');
  await expect(page.getByRole('heading', { name: 'Mapa de leitos' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  await page.goto('/admissoes/nova/');
  await expect(page.getByRole('heading', { name: 'Nova admissão' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('/transferencias/nova/');
  await expect(page.getByRole('heading', { name: 'Transferir internação' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  await page.goto('/altas/nova/');
  await expect(page.getByRole('heading', { name: 'Registrar alta' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);
});
