const { test, expect } = require('@playwright/test');

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

async function selectOptionContaining(select, text) {
  const value = await select.locator('option').evaluateAll((options, expected) => {
    const option = options.find((item) => item.value && item.textContent.includes(expected));
    return option ? option.value : null;
  }, text);
  expect(value, `Opção contendo "${text}" deve existir`).toBeTruthy();
  await select.selectOption(value);
}

test('prescrever, submeter, validar e dispensar por lote preserva o fluxo clínico', async ({ page }) => {
  await login(page);

  await page.goto('/prescricoes/nova/');
  await expect(page.getByRole('heading', { name: 'Nova prescrição' })).toBeVisible();
  await selectOptionContaining(page.getByLabel('Encontro'), 'Paciente Sintético RX E2E');
  await selectOptionContaining(page.getByLabel('Medicamento'), 'Medicamento Sintético Acessibilidade');
  await page.getByLabel('Dose', { exact: true }).fill('10');
  await page.getByLabel('Unidade da dose').fill('mg');
  await page.getByLabel('Via').fill('oral');
  await page.getByLabel('Frequência').fill('1x ao dia');
  await page.getByRole('button', { name: 'Salvar rascunho' }).click();

  await expect(page.getByRole('heading', { name: 'Prescrição' })).toBeVisible();
  await expect(page.getByText(/Status: Rascunho/)).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();

  await page.getByLabel('Confirmo a submissão da prescrição').check();
  await page.getByRole('button', { name: 'Submeter' }).click();
  await expect(page.getByText('Prescrição submetida para validação farmacêutica.')).toBeVisible();
  await expect(page.getByText(/Status: Submetida/)).toBeVisible();

  await page.getByRole('link', { name: 'Validar' }).click();
  await expect(page.getByRole('heading', { name: 'Validação farmacêutica' })).toBeVisible();
  await expect(page.getByText('Checagem automática de alergias indisponível.')).toBeVisible();
  await expect(page.getByText('NOT_EVALUABLE')).toBeVisible();
  await page
    .getByLabel(/Revisei manualmente a situação de alergias/)
    .check();
  await page.getByLabel('Confirmo a validação farmacêutica').check();
  await page.getByRole('button', { name: 'Validar prescrição' }).click();

  await expect(page.getByText('Prescrição validada com sucesso.')).toBeVisible();
  await expect(page.getByText(/Status: Validada/)).toBeVisible();
  await page.getByRole('link', { name: 'Dispensar' }).click();

  await expect(page.getByRole('heading', { name: 'Dispensação por lote' })).toBeVisible();
  await selectOptionContaining(
    page.getByLabel('Item prescrito'),
    'Medicamento Sintético Acessibilidade',
  );
  await selectOptionContaining(page.getByLabel('Lote'), 'E2E-RX-LOT-A11Y-001');
  await page.getByLabel('Quantidade').fill('1');
  await page.getByLabel('Confirmo a dispensação e a baixa de estoque').check();
  await page.getByRole('button', { name: 'Confirmar dispensação' }).click();

  await expect(page.getByRole('heading', { name: 'Dispensação concluída' })).toBeVisible();
  await expect(page.getByText('E2E-RX-LOT-A11Y-001')).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();
});

test('interação sintética bloqueante impede validação sem perder a revisão', async ({ page }) => {
  await login(page);
  await page.goto('/prescricoes/');
  await expect(page.getByRole('heading', { name: 'Prescrições' })).toBeVisible();

  const row = page
    .getByRole('row')
    .filter({ hasText: 'Submetida' })
    .filter({ hasText: 'Paciente Sintético RX E2E' })
    .first();
  await expect(row).toBeVisible();
  await row.getByRole('link', { name: 'Abrir' }).click();
  await page.getByRole('link', { name: 'Validar' }).click();

  await expect(page.getByRole('heading', { name: 'Validação farmacêutica' })).toBeVisible();
  await page.getByLabel(/Revisei manualmente a situação de alergias/).check();
  await page.getByLabel('Confirmo a validação farmacêutica').check();
  await page.getByRole('button', { name: 'Validar prescrição' }).click();

  await expect(page.getByText(/achado de segurança bloqueante/i)).toBeVisible();
  await expect(page.getByText('Interação sintética bloqueante E2E')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Validar prescrição' })).toBeVisible();
});