# Exportação de paciente — Spec 012 v1

## Habilitação e uso

Execute `python manage.py migrate`. A migration cria recibos técnicos e a permissão `interoperability.export_patient`; nenhum grupo recebe a permissão automaticamente.

No Django Admin existente, um administrador autorizado pode atribuir a permissão **Pode exportar cadastro mínimo de paciente** ao profissional/grupo apropriado. O profissional deve ter papel interno (`ADM`/`FUNC`) e acesso atual ao paciente no PEP. A permissão de exportar não concede acesso a outros pacientes. Superusuários seguem a semântica nativa de permissões do Django.

No menu **Clínico → Exportar paciente**, selecione um paciente, confirme a guarda do arquivo e clique em **Baixar arquivo**. O arquivo contém apenas UUID local, cadastro ativo, nome completo e data de nascimento. CPF, contatos, sexo e informações assistenciais são excluídos. O formato é Patient FHIR R4 JSON; não é prontuário completo nem perfil nacional certificado.

O formulário requer conexão. Não existe exportação em lote, fila offline ou envio automático a terceiros. Sair do sistema não apaga um arquivo que o usuário já baixou; sua guarda segue a política institucional. A confirmação do formulário não constitui consentimento do paciente.

## Auditoria e falhas

Cada geração cria um `PatientExportReceipt` com paciente, ator, horário, contrato e SHA-256 dos bytes. O nome do arquivo inclui apenas o UUID do recibo. Auditoria ACCESS do paciente e CREATE do recibo são persistidas na mesma transação. Falha de banco durante essa persistência retorna 503 genérico e impede entrega do arquivo.

O recibo comprova geração, não recebimento por outro sistema. Repetir uma exportação gera outro recibo; o arquivo não fica armazenado no servidor. O hash permite conferir um arquivo apresentado, mas não reconstruir o cadastro histórico. Recibos não possuem tela de edição/exclusão nem registro no admin.

## Verificação e rollback

```bash
uv run python manage.py test apps.interoperability
uv run python tests/e2e/prepare_interop_journeys.py
npx playwright test --config=playwright.config.cjs tests/e2e/interop_journeys.spec.js
```

A preparação E2E cria contas com senhas públicas e pacientes sintéticos: executar **somente em banco descartável de teste**, junto às demais preparações E2E da CI. Não executar em produção.

Para desabilitar o piloto, revogue a capacidade dos grupos/usuários participantes. Superusuários ainda possuem permissões globais; rollback de código remove a interface. Preserve a tabela e os recibos após uso real. `migrate interoperability zero` é destrutivo e foi validado apenas em banco descartável, antes de dados reais.

Resultados e limitações: [validação da Spec 012](../specs/012-interoperabilidade/validation.md). Não foram adicionadas API REST pública, dependências de aplicação ou novas operações PWA.
