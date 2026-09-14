const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const PROFESSIONAL = {
  username: 'ci-pep-professional',
  password: 'ci-pep-professional-password',
};
const OUTSIDER = {
  username: 'ci-pep-outsider',
  password: 'ci-pep-outsider-password',
};

async function login(page, credentials) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(credentials.username);
  await page.getByLabel('Senha').fill(credentials.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function createPatient(page, { identifier, name }) {
  await page.goto('/pacientes/novo/');
  await page.getByLabel('Tipo de identificador').selectOption('OTHER');
  await page.getByLabel('CPF ou identificador').fill(identifier);
  await page.getByLabel('Nome completo').fill(name);
  await page.getByLabel('Data de nascimento').fill('1990-01-15');
  await page.getByLabel('Sexo').selectOption('F');
  await page.getByRole('button', { name: 'Salvar paciente' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  return page.url();
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

test('profissional percorre paciente, encontro, evolução e adendo sem perder o original', async ({
  page,
  browser,
}) => {
  const patientName = 'Pessoa Sintética Jornada E2E';
  const originalContent = 'Registro sintético de evolução E2E, sem dado real.';
  const amendmentContent = 'Adendo sintético E2E para validar histórico append-only.';

  await login(page, PROFESSIONAL);
  const patientUrl = await createPatient(page, {
    identifier: 'E2E-PEP-JOURNEY-001',
    name: patientName,
  });

  await page.getByRole('link', { name: 'Novo encontro clínico' }).click();
  await page.getByLabel('Início do atendimento').fill('2026-09-14T08:00');
  await page.getByLabel('Local').fill('Sala E2E');
  await page.getByLabel('Motivo do atendimento').fill('Contexto sintético de teste E2E.');
  await page.getByRole('button', { name: 'Iniciar encontro' }).click();

  await expect(page.getByRole('heading', { name: 'Consulta' })).toBeVisible();
  await expect(page.getByText('Sala E2E')).toBeVisible();
  await page.getByRole('link', { name: 'Nova evolução' }).click();
  await page.getByLabel('Evolução clínica').fill(originalContent);
  await page.getByRole('button', { name: 'Salvar evolução' }).click();

  await expect(page.getByRole('heading', { name: 'Evolução clínica' })).toBeVisible();
  await expect(page.getByText(originalContent)).toBeVisible();
  const originalUrl = page.url();

  await page.getByRole('link', { name: 'Registrar adendo' }).click();
  await page.getByLabel('Motivo do adendo').fill('Complementação sintética E2E');
  await page.getByLabel('Conteúdo do adendo').fill(amendmentContent);
  await page.getByRole('button', { name: 'Salvar adendo' }).click();

  await expect(page.getByRole('heading', { name: 'Adendo clínico' })).toBeVisible();
  await expect(page.getByText('Motivo: Complementação sintética E2E')).toBeVisible();
  await expect(page.getByText(amendmentContent)).toBeVisible();

  await page.goto(originalUrl);
  await expect(page.getByText(originalContent)).toBeVisible();
  await expect(page.getByText(amendmentContent)).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Ver adendo →' })).toBeVisible();

  const outsiderContext = await browser.newContext();
  const outsiderPage = await outsiderContext.newPage();
  await login(outsiderPage, OUTSIDER);
  const denied = await outsiderPage.goto(patientUrl);
  expect(denied.status()).toBe(404);
  expect(await denied.text()).not.toContain(patientName);
  await outsiderContext.close();
});

test('PEP não apresenta violações sérias e mantém layout essencial em telefone e tablet', async ({
  page,
}) => {
  const patientName = 'Pessoa Sintética Acessibilidade E2E';

  await login(page, PROFESSIONAL);
  const patientUrl = await createPatient(page, {
    identifier: 'E2E-PEP-A11Y-001',
    name: patientName,
  });

  await page.goto('/pacientes/');
  await expectNoSeriousAxeViolations(page);

  await page.goto(patientUrl);
  await expectNoSeriousAxeViolations(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/pacientes/');
  await expect(page.getByRole('heading', { name: 'Pacientes' })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.goto(patientUrl);
  await expect(page.getByRole('heading', { name: patientName })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Novo encontro clínico' })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.setViewportSize({ width: 768, height: 1024 });
  await page.getByRole('link', { name: 'Novo encontro clínico' }).click();
  await expect(page.getByRole('heading', { name: 'Novo encontro clínico' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);
});
