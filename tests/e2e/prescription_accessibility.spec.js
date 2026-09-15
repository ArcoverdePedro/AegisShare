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

async function verifyDrugCreateForm(page) {
  await page.goto('/medicamentos/novo/');
  await expect(page.getByRole('heading', { name: 'Novo medicamento' })).toBeVisible();
  await expect(page.getByLabel('Código interno')).toBeVisible();
  await expect(page.getByLabel('Medicamento')).toBeVisible();
  await expect(page.getByLabel('Apresentação')).toBeVisible();
  await expect(page.getByLabel('Concentração / força')).toBeVisible();
  await expect(page.getByLabel('Via sugerida (informativa)')).toBeVisible();
  await expect(page.getByLabel('Unidade de dispensação')).toBeVisible();
  await expect(page.getByLabel('Ativo para novas prescrições')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Salvar medicamento' })).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyDrugEditForm(page) {
  await page.goto('/medicamentos/');
  const primaryRow = page
    .getByRole('row')
    .filter({ hasText: 'Medicamento Sintético Acessibilidade' });
  await primaryRow.getByRole('link', { name: 'Editar' }).click();
  await expect(page.getByRole('heading', { name: 'Editar medicamento' })).toBeVisible();
  await expect(page.getByLabel('Código interno')).toHaveValue('E2E-RX-A11Y-001');
  await expect(page.getByLabel('Medicamento')).toHaveValue('Medicamento Sintético Acessibilidade');
  await expect(page.getByRole('button', { name: 'Salvar medicamento' })).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyStock(page) {
  await page.goto('/estoque-farmacia/');
  await expect(page.getByRole('heading', { name: 'Estoque farmacêutico' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();
  await expect(page.getByText('E2E-RX-LOT-A11Y-001')).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyPrescriptionList(page) {
  await page.goto('/prescricoes/');
  await expect(page.getByRole('heading', { name: 'Prescrições' })).toBeVisible();
  await expect(page.getByText('Paciente Sintético RX E2E').first()).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyPrescriptionCreate(page) {
  await page.goto('/prescricoes/nova/');
  await expect(page.getByRole('heading', { name: 'Nova prescrição' })).toBeVisible();
  await expect(page.getByLabel('Encontro')).toBeVisible();
  const item = page.getByRole('group', { name: 'Item 1' });
  await expect(item.getByLabel('Medicamento')).toBeVisible();
  await expect(item.getByLabel('Dose', { exact: true })).toBeVisible();
  await expect(item.getByLabel('Unidade da dose', { exact: true })).toBeVisible();
  await expect(item.getByLabel('Via')).toBeVisible();
  await expect(item.getByLabel('Frequência')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Salvar rascunho' })).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyValidation(page) {
  await page.goto('/prescricoes/');
  const submittedRow = page.getByRole('row').filter({ hasText: 'Submetida' }).first();
  await expect(submittedRow).toBeVisible();
  await submittedRow.getByRole('link', { name: 'Abrir' }).click();
  await page.getByRole('link', { name: 'Validar' }).click();
  await expect(page.getByRole('heading', { name: 'Validação farmacêutica' })).toBeVisible();
  await expect(page.getByLabel(/Revisei manualmente a situação de alergias/)).toBeVisible();
  await expect(page.getByLabel('Confirmo a validação farmacêutica')).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyDispense(page) {
  await page.goto('/prescricoes/');
  const validatedRow = page.getByRole('row').filter({ hasText: 'Validada' }).first();
  await expect(validatedRow).toBeVisible();
  await validatedRow.getByRole('link', { name: 'Abrir' }).click();
  await page.getByRole('link', { name: 'Dispensar' }).click();
  await expect(page.getByRole('heading', { name: 'Dispensação por lote' })).toBeVisible();
  const item = page.getByRole('group', { name: 'Item de dispensação 1' });
  await expect(item.getByLabel('Item prescrito')).toBeVisible();
  await expect(item.getByLabel('Lote')).toBeVisible();
  await expect(item.getByLabel('Quantidade')).toBeVisible();
  await expect(page.getByLabel('Confirmo a dispensação e a baixa de estoque')).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyDispenseList(page) {
  await page.goto('/dispensacoes/');
  await expect(page.getByRole('heading', { name: 'Dispensações' })).toBeVisible();
  await expectNoPageOverflow(page);
}

async function verifyPublishedSurfaces(page) {
  const checks = [
    verifyCatalog,
    verifyDrugCreateForm,
    verifyDrugEditForm,
    verifyStock,
    verifyPrescriptionList,
    verifyPrescriptionCreate,
    verifyValidation,
    verifyDispense,
    verifyDispenseList,
  ];
  for (const verify of checks) {
    await verify(page);
    await expectNoSeriousAxeViolations(page);
  }
}

test('superfícies RX publicadas não apresentam violações sérias WCAG', async ({ page }) => {
  await login(page);
  await verifyPublishedSurfaces(page);
});

test('superfícies RX publicadas preservam layout essencial em telefone e tablet', async ({ page }) => {
  await login(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await verifyPublishedSurfaces(page);

  await page.setViewportSize({ width: 768, height: 1024 });
  await verifyPublishedSurfaces(page);
});
