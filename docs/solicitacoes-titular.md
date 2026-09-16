# Solicitações do titular — Spec 013 v1

## Habilitar o fluxo

Execute `python manage.py migrate`. A migration `compliance.0001_initial` cria solicitações, eventos e capacidades. Nenhum grupo recebe novas permissões automaticamente.

Use o Django Admin existente para atribuir as capacidades aos grupos/profissionais apropriados:

| Capacidade | Uso |
|---|---|
| `compliance.view_requests` | consultar lista, detalhe e histórico; pré-requisito das demais |
| `compliance.register_request` | registrar solicitação |
| `compliance.process_request` | iniciar análise e encerrar administrativamente |

O usuário deve ser profissional interno (`ADM` ou `FUNC`) e ter acesso atual ao paciente no PEP. A capacidade não cria acesso clínico. Superusuários seguem as regras globais do Django. Pacientes inativos estão fora do queryset PEP atual; esta versão não amplia essa política.

## Registrar e acompanhar

No menu **Clínico → Solicitações do titular**, escolha **Nova solicitação**, selecione o paciente, a categoria e informe um resumo necessário ao atendimento. O sistema cria um protocolo e o evento **Recebida**, com ator e horário do servidor.

No detalhe, **Iniciar análise** permite uma nota opcional. Depois, **Encerrar administrativamente** exige nota. O histórico permanece visível; não há edição de texto, exclusão de evento ou reabertura nesta versão.

Encerrar registra o acompanhamento administrativo. Não significa deferimento, exclusão/correção de dados, exportação, consentimento, validação de identidade ou comunicação ao titular. Esses procedimentos continuam sujeitos à governança institucional.

Se outro operador atualizar a mesma solicitação, um formulário antigo retorna conflito e orienta consultar o histórico. A nota já gravada não é sobrescrita. Reenviar uma transição confirmada também produz conflito. Duas novas solicitações não são unificadas automaticamente por nome, categoria ou texto.

## Privacidade e operação

As telas exigem conexão. Não há envio automático a terceiros, fila offline, push ou cópia de resumo/notas no auditlog genérico. As leituras da lista e detalhe são auditadas; só os objetos apresentados na página são registrados como acessados.

Não inclua credenciais, documentos de identidade ou cópias de prontuário em resumo/notas. Permissões e auditoria técnica não substituem o procedimento institucional para receber e conferir solicitações, atender ao titular e definir retenção.

Falhas de banco na criação/transição retornam erro genérico e revertem solicitação/estado, evento e auditoria da operação. Consulte novamente o histórico após qualquer falha de conectividade; uma resposta perdida pode corresponder a uma operação já confirmada no servidor.

## Verificação e rollback

```bash
uv run python manage.py test apps.compliance
uv run python tests/e2e/prepare_compliance_journeys.py
npx playwright test --config=playwright.config.cjs tests/e2e/compliance_journeys.spec.js
```

A preparação E2E cria credenciais públicas e dados sintéticos. Execute-a somente em banco descartável de teste. O teste de concorrência requer PostgreSQL; SQLite não valida o bloqueio de linha.

Para retirar acesso ao piloto, revogue as capacidades dos usuários/grupos. Superusuários conservam acesso global; rollback do código remove a interface. Preserve as tabelas e o histórico após uso real. A reversão destrutiva `migrate compliance zero` foi testada apenas em banco descartável.

Consulte [spec e rastreabilidade](../specs/013-lgpd-anvisa/spec.md) e [evidências](../specs/013-lgpd-anvisa/validation.md).
