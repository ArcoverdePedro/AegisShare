# Rastreabilidade — Spec 003 Prescrição e Farmácia

> Baseline de fechamento técnico: 2026-09-15.  
> A matriz abaixo descreve o runtime efetivamente entregue após os fluxos de prescrição, validação e dispensação. O único gate clínico de conteúdo ainda aberto nesta spec é T-RX-02; nenhum dado terapêutico real é inventado para fechar checklist.

## Gates externos preservados

- **T-RX-02:** fonte/conteúdo real de `Interaction` e `DoseRule` depende de validação clínica/farmacêutica institucional. O código aceita somente referências estruturadas, versionadas e aprovadas; testes usam fixtures sintéticas.
- **Alergias estruturadas:** a extensão PEP está especificada em `specs/001-pep/extensions/allergy-intolerance/`, porém a checagem automática permanece desabilitada até governança/implementação própria. RX declara indisponibilidade e exige revisão manual explícita.
- **Peso estruturado:** não existe fonte clínica aprovada nesta versão. Regras dependentes de peso retornam `NOT_EVALUABLE`; nenhum peso é estimado.
- **Assinatura jurídica:** validação farmacêutica não equivale à assinatura eletrônica de T-PEP-08.

## Requisitos funcionais

| Requisito | Estado técnico | Evidência principal |
|---|---|---|
| **RF-RX-01 — Catálogo** | **Implementado** | `Drug`, catálogo/formulário server-rendered, `catalog_services.py`, governança/imutabilidade de referências e testes de catálogo. |
| **RF-RX-02 — Prescrição vinculada ao PEP** | **Implementado** | `MedicationRequest`, `prescription_list`, `prescription_create`, `prescription_detail`; autorização exige capacidade RX + escopo PEP. |
| **RF-RX-03 — Itens estruturados** | **Implementado** | `MedicationRequestItem`, `MedicationRequestItemFormSet`, services server-side e validações de dose/via/frequência/duração. |
| **RF-RX-04 — Histórico imutável** | **Implementado** | Guards de aplicação/PostgreSQL, submissão que congela DRAFT, substituição rastreável, cancelamento sem exclusão e safety/dispense append-only. |
| **RF-RX-05 — Interações** | **Implementado com gate de conteúdo T-RX-02** | `safety.py` considera somente `Interaction` ativa e aprovada; `blocking=True` vem do dado governado e impede validação. |
| **RF-RX-06 — Alergias** | **Implementado em modo fail-safe** | `AllergyStatus.UNAVAILABLE/REVIEW_CONFIRMED`; UI exige revisão manual e nunca afirma “sem alergias conhecidas”. Automação estruturada permanece bloqueada pela extensão PEP. |
| **RF-RX-07 — Dose idade/peso** | **Implementado em modo determinístico/fail-safe** | `DoseRule` aprovada é avaliada sem expressão arbitrária; idade vem do PEP e peso/fato ausente produz `NOT_EVALUABLE`. |
| **RF-RX-08 — Validação farmacêutica** | **Implementado** | `validate_medication_request`, `MedicationSafetyReview`/`Finding`, `/prescricoes/<uuid>/validar/` e evento `prescription.validated`. |
| **RF-RX-09 — Estoque** | **Implementado** | `StockItem`, `Lot`, `StockMovement`, services atômicos, validade/saldo/baixo estoque e `/estoque-farmacia/`. |
| **RF-RX-10 — Dispensação transacional** | **Implementado** | `dispense_services.py`: `transaction.atomic()`, locks `select_for_update()`, `operation_key`, saldo/validade/lote revalidados e rollback seguro. |
| **RF-RX-11 — Rastreabilidade por lote** | **Implementado** | `MedicationDispense -> MedicationDispenseItem -> Lot -> StockMovement`, todos históricos/append-only. |
| **RF-RX-12 — Autorização** | **Implementado** | `permissions.py`, selectors, escopo PEP, papel `CLI` deny-by-default, testes unitários + Gherkin + Playwright de negação. |
| **RF-RX-13 — Auditoria/eventos** | **Implementado** | auditlog com ator explícito; textos sensíveis excluídos; AsyncAPI e quatro eventos pós-commit: `prescription.created`, `prescription.validated`, `medication.dispensed`, `stock.low`. |
| **RF-RX-14 — PWA network-only** | **Implementado** | arquitetura e Playwright provam que prescrição/validação/dispensação não entram em Cache Storage/IndexedDB e falham offline sem fila. |

## Requisitos não funcionais

| Requisito | Estado | Evidência |
|---|---|---|
| **RNF-RX-01 — PostgreSQL fonte de verdade** | **Implementado** | CI aplica migrations e testes contra PostgreSQL; invariantes críticas também são protegidas no banco. |
| **RNF-RX-02 — Estoque atômico/concorrente** | **Implementado** | locks, transações, constraint de saldo não negativo e testes `TransactionTestCase` concorrentes. |
| **RNF-RX-03 — Sem REST público** | **Implementado** | URLConf server-rendered/POST tradicional e `test_architecture.py` bloqueando superfície `/api/`. |
| **RNF-RX-04 — Minimização de PHI** | **Implementado** | allowlists de eventos, auditlog exclui texto clínico livre e respostas de negação não renderizam PHI. |
| **RNF-RX-05 — WCAG/responsivo** | **Implementado** | `tests/e2e/prescription_accessibility.spec.js`: axe WCAG 2.1 A/AA + telefone 390×844 + tablet 768×1024 nas telas essenciais. |
| **RNF-RX-06 — Referências governadas** | **Estrutura implementada; conteúdo real bloqueado por T-RX-02** | procedência, versão, aprovador/data, ativação controlada e imutabilidade de versão aprovada. |
| **RNF-RX-07 — Migrations reversíveis** | **Implementado** | migrations RX versionadas/reversíveis; guards PostgreSQL têm reverso explícito. |
| **RNF-RX-08 — Idempotência/conflito seguro** | **Implementado** | `MedicationDispense.operation_key` única + comparação da operação repetida + mensagens seguras e rollback. |

## Superfícies RX publicadas

Todas permanecem internas, autenticadas por sessão e com respostas clínicas `private, no-store, max-age=0` quando aplicável:

- `/prescricoes/`
- `/prescricoes/nova/`
- `/prescricoes/<uuid>/`
- `/prescricoes/<uuid>/submeter/`
- `/prescricoes/<uuid>/validar/`
- `/prescricoes/<uuid>/cancelar/`
- `/prescricoes/<uuid>/dispensar/`
- `/dispensacoes/`
- `/dispensacoes/<uuid>/`
- `/medicamentos/`
- `/medicamentos/novo/`
- `/medicamentos/<uuid>/editar/`
- `/estoque-farmacia/`

Nenhuma rota REST pública foi criada.

## Evidências automatizadas principais

- **Lifecycle/modelos/integridade:** `test_models.py`, `test_services.py`, `test_request_history_integrity.py`, `test_append_only_integrity.py`, `test_database_integrity_guards.py`, `test_request_identity_integrity.py`.
- **Safety + dispensação:** `test_safety_and_dispense.py`, `test_stock.py`, `test_stock_concurrency.py`, `test_stock_identity_db_guards.py`.
- **RBAC/ABAC:** `test_permissions.py`, `test_selectors.py`, `test_anonymous_boundary.py`, `test_denied_access_audit.py`, `test_acceptance_traceability.py`, `features/authorization.feature`, `prescription_authorization.spec.js`.
- **Auditoria/eventos:** `test_event_contract.py`, `test_prescription_audit_actor.py`, `test_stock_audit_actor.py`, `test_auditlog_sensitive_fields.py`, `test_audit_events.py`.
- **Jornada clínica:** `specs/003-prescricao-farmacia/features/clinical_journeys.feature` e `tests/e2e/prescription_clinical_flows.spec.js`.
- **Acessibilidade/mobile:** `tests/e2e/prescription_accessibility.spec.js`.
- **PWA/network-only:** `test_architecture.py`, `test_response_cache_policy.py`, `tests/e2e/prescription_pwa_boundary.spec.js`.
- **Integração com Enfermagem (Spec 004):** `MedicationAdministration -> MedicationDispenseItem`, contratos em `specs/004-enfermagem/contracts/medication-administration.md` e testes de serviço/view/auditoria da administração.

## Definition of Done

A implementação técnica da Spec 003 está concluída para o escopo aprovado. A integração prevista com a Spec 004 também está concluída e mantém a cadeia de rastreabilidade até dispensação/prescrição/lote. O fechamento global da spec permanece administrativamente aberto apenas onde o SDD ainda depende de terceiros ou de contexto futuro: **T-RX-02** (governança clínica real) e **T-RX-17** (fronteira futura com a Spec 009). Isso é um bloqueio explícito, não uma lacuna escondida de código.
