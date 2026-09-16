# Rastreabilidade — Spec 004 Enfermagem

> Estado: implementação v1 concluída em 2026-09-16. Permanecem abertos somente os gates externos T-NUR-09 e T-NUR-11, que não autorizam comportamento clínico adicional enquanto não houver decisão de governança.

## Matriz final

| Requisito | Contrato/decisão | Código implementado | Evidência automatizada |
|---|---|---|---|
| RF-NUR-01 | `spec.md`, `contracts/access-policy.md` | `models.py`, `permissions.py`, `views.py` sobre `PEP.Encounter` | `test_permissions.py`, `test_views.py`, `test_administration_views.py` |
| RF-NUR-02 | `data-model.md` | `VitalSignsRecord`, `VitalSignsRecordForm`, FBVs de sinais vitais | `test_models.py`, `test_forms.py`, `test_views.py` |
| RF-NUR-03 | `data-model.md` | campos estruturados em unidades canônicas; sem interpretação clínica | `test_models.py`, `test_forms.py` |
| RF-NUR-04 | `data-model.md` | `recorded_at` + `created_at` e validação temporal em form/service | `test_forms.py`, `test_services.py`, `test_offline_sync.py` |
| RF-NUR-05 | `data-model.md` | `replaces` + criação append-only em `services.py`/`views.py` | `test_models.py`, `test_services.py`, `test_views.py` |
| RF-NUR-06 | `contracts/offline-vital-signs.md` | `vitals_form.html` + `AegisOfflineQueue` existente + `vitals_sync` | `test_offline_sync.py`, `tests/e2e/nursing_offline.spec.js`, `tests/e2e/nursing_local_data_privacy.spec.js` |
| RF-NUR-07 | `contracts/offline-vital-signs.md` | revalidação server-side e idempotência em `views.py`/`services.py` | `test_offline_sync.py`, `test_services.py`, `tests/e2e/nursing_offline.spec.js` |
| RF-NUR-08 | `data-model.md`, gate T-NUR-09 | `latest_weight_fact()` em `selectors.py`, sem decidir elegibilidade clínica | `test_selectors.py`, `test_weight_rx_gate.py` |
| RF-NUR-09 | `contracts/medication-administration.md` | `MedicationAdministration` -> `MedicationDispenseItem` -> prescrição/lote | `test_administration_services.py`, `test_administration_views.py`, `tests/e2e/nursing_medication_administration.spec.js` |
| RF-NUR-10 | `contracts/medication-administration.md` | `MedicationAdministrationForm` + `administer_medication()` sem conversão/inferência | `test_forms.py`, `test_administration_services.py` |
| RF-NUR-11 | `contracts/medication-administration.md` | `operation_key` UUID única + retry idempotente | `test_administration_services.py`, `test_administration_views.py` |
| RF-NUR-12 | contratos offline/administração | administração somente por POST HTML online; sem integração com fila PWA | `test_administration_views.py`, `tests/e2e/nursing_medication_administration.spec.js` |
| RF-NUR-13 | `contracts/access-policy.md` | capacidades `view_nursing`, `record_vitals`, `administer_medication` + escopo PEP | `test_permissions.py`, `test_views.py`, `test_administration_views.py`, `test_audit_events.py` |
| RF-NUR-14 | `contracts/events.asyncapi.yaml` | `events.py`, `set_actor()` nos services, `ACCESS` nas leituras e `transaction.on_commit()` | `test_audit_events.py` |
| RNF-NUR-01 | `data-model.md` | modelos Django persistidos no PostgreSQL; migration `0001_initial.py` | suíte Django em PostgreSQL no CI |
| RNF-NUR-02 | `data-model.md` | services append-only; nenhuma edição/exclusão clínica destrutiva pela UI | `test_models.py`, `test_services.py`, `test_administration_services.py` |
| RNF-NUR-03 | `contracts/routes.md` | FBVs em `apps/clinical/nursing/urls.py`; todas as rotas sob `/enfermagem/` | `aegis_share/tests/test_architecture.py::PublicApiArchitectureTests` |
| RNF-NUR-04 | contratos de eventos/offline | auditlog com campos clínicos excluídos, eventos mínimos e logging sem payload clínico | `test_audit_events.py`, `tests/e2e/nursing_local_data_privacy.spec.js`, gate de logs em `.github/workflows/django.yml` |
| RNF-NUR-05 | `spec.md` | templates server-rendered responsivos | `tests/e2e/nursing_offline.spec.js`, `tests/e2e/nursing_medication_accessibility.spec.js` com axe-core e telefone/tablet |
| RNF-NUR-06 | contratos offline/administração | `idempotency_key`/`operation_key` e conflitos seguros | `test_offline_sync.py`, `test_services.py`, `test_administration_services.py`, Playwright |
| RNF-NUR-07 | `plan.md` | `apps/clinical/nursing/migrations/0001_initial.py` | `makemigrations --check --dry-run` + aplicação da migration em PostgreSQL no CI |
| RNF-NUR-08 | `contracts/offline-vital-signs.md` | reutilização exclusiva de `static/pwa/offline_queue.js`; nenhum segundo mecanismo offline | `tests/e2e/nursing_offline.spec.js`, `tests/e2e/nursing_local_data_privacy.spec.js`, testes PWA existentes |

## Rastreabilidade de aceitação

O Gherkin canônico permanece em `features/acceptance.feature`. `apps/clinical/nursing/tests/test_acceptance_traceability.py` exige títulos compartilhados com as jornadas Playwright para os fluxos principais de sinais vitais e administração. Os E2E concretos são:

- `tests/e2e/nursing_offline.spec.js` — sinais vitais online, fila cifrada, retry e conflito por encontro encerrado;
- `tests/e2e/nursing_medication_administration.spec.js` — administração online e prova de comportamento network-only;
- `tests/e2e/nursing_medication_accessibility.spec.js` — axe-core e responsividade em 390x844 e 768x1024;
- `tests/e2e/nursing_local_data_privacy.spec.js` — ausência de plaintext clínico em IndexedDB/Cache Storage/console e limpeza da fila no logout.

## API pública

A Spec 004 não adiciona API REST pública. `apps/clinical/nursing/urls.py` registra somente superfícies sob `/enfermagem/`, incluindo a sincronização interna autenticada por sessão e CSRF em `/enfermagem/sinais-vitais/sincronizar/`.

A proteção não depende apenas desta documentação: `aegis_share/tests/test_architecture.py::PublicApiArchitectureTests.test_no_new_public_api_routes_are_introduced` coleta todas as rotas do projeto iniciadas por `api/` e exige igualdade com a allowlist legada de três rotas de arquivos. Qualquer nova rota pública `/api/` faz a suíte falhar.

## Eventos internos

`contracts/events.asyncapi.yaml` descreve os dois eventos implementados:

- `nursing.vitals.recorded`;
- `nursing.medication.administered`.

`apps/clinical/nursing/tests/test_audit_events.py` mantém a allowlist de nomes alinhada ao AsyncAPI e valida payload mínimo. O envelope técnico `type=nursing_event_handler` existe apenas no transporte Django Channels e não faz parte do payload de domínio contratado.

## Gates externos rastreados

| Gate | Impacto | Estado |
|---|---|---|
| T-NUR-09 — política de atualidade/origem do peso | impede consumo automático do peso pelo RX | BLOCKED governança clínica/farmacêutica |
| T-NUR-11 — exceções de administração | impede modelar recusa/omissão/atraso/dose divergente | BLOCKED governança clínica/operacional |
| faixas de normalidade/alertas | impede interpretação automática de sinais vitais | fora de escopo até referência aprovada |

Enquanto esses gates permanecerem abertos, nenhuma implementação deve inferir elegibilidade de peso, exceções de administração ou normalidade de sinais vitais.

## Dependências cruzadas

- Spec 001 fornece paciente, encontro e escopo clínico.
- Spec 002 pode fornecer contexto de local/leito, sem ampliar acesso PEP.
- Spec 003 fornece prescrição, dispensação e lote; continua `NOT_EVALUABLE` para peso até fechamento do gate correspondente.
- Spec 014 fornece fila local cifrada, chave não extraível, limpeza no logout e contrato geral de sincronização.

## Critério de fechamento da v1

A implementação v1 está pronta para fechamento porque:

1. todos os itens não bloqueados de `tasks.md` foram implementados;
2. a suíte Django, migrations, staticfiles, compileall, Docker Compose, Playwright e Lighthouse integram o CI determinístico;
3. Gherkin/Playwright cobrem jornadas online/offline, retry, conflito e administração network-only;
4. axe-core e telefone/tablet possuem gate automatizado;
5. armazenamento local, cache, console e logs possuem regressões contra plaintext clínico no piloto offline;
6. a arquitetura global impede criação silenciosa de nova `/api/` pública;
7. T-NUR-09 e T-NUR-11 permanecem explicitamente bloqueados, sem comportamento clínico especulativo.
