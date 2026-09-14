# Rastreabilidade — Spec 003 Prescrição e Farmácia

> Baseline técnica: `master` em `a262b2ab8969a3e804f8db843505f6bfcc5342c4`, 2026-09-14.  
> Esta matriz descreve o estado efetivamente disponível no repositório. Rotas/telas previstas na `spec.md` não são tratadas como implementadas até existirem no `urls.py` e possuírem cobertura correspondente.

## Legenda

- **Implementado** — requisito coberto no escopo atualmente disponível, com evidência automatizada.
- **Parcial** — fundação ou parte do fluxo existe, mas o requisito ainda depende de uma etapa futura.
- **Pendente** — fluxo ainda não foi implementado.
- **Gate clínico** — implementação automática depende de governança/fonte clínica aprovada e não deve ser antecipada com regra inventada no código.

## Requisitos funcionais

| Requisito | Estado | Implementação / evidência atual | Lacuna para fechamento |
|---|---|---|---|
| **RF-RX-01 — Catálogo de medicamentos** | **Implementado** | `models.py` (`Drug`), `forms.py`, `views.py`, `urls.py`; templates `drug_catalog.html`/`drug_form.html`; `tests/test_catalog.py`; axe/E2E em `tests/e2e/prescription_accessibility.spec.js`. Medicamento já utilizado em prescrição tem significado histórico congelado em aplicação e PostgreSQL por `0006_used_drug_integrity.py`, com prova em `test_used_drug_integrity.py`; `active` permanece mutável. | Conteúdo clínico real de referências continua subordinado a T-RX-02/RNF-RX-06. |
| **RF-RX-02 — Prescrição vinculada ao PEP** | **Parcial** | `MedicationRequest`, `services.py::create_medication_request`, RBAC+ABAC em `permissions.py`; `tests/test_services.py`, `test_permissions.py`, `test_selectors.py`. | Não existe rota/tela de criação de prescrição em `apps/clinical/prescription/urls.py`; jornada server-rendered permanece pendente. |
| **RF-RX-03 — Itens estruturados** | **Parcial** | `MedicationRequestItem`, services de inclusão/remoção/submissão e validações server-side; `tests/test_models.py`, `test_services.py`. | Formulário/tela final de prescrição ainda não existe. |
| **RF-RX-04 — Histórico imutável** | **Implementado** | Services e signals restringem mutação ao DRAFT. `0004_database_mutation_guards.py` impede update/delete de registros append-only e mutação de item fora de DRAFT; `0006_used_drug_integrity.py` preserva o significado do medicamento já prescrito; `0008_request_history_guards.py` congela encontro, autor, substituição, criação e horário de submissão quando a prescrição sai de DRAFT. Cobertura: `test_request_history_integrity.py`, `test_append_only_integrity.py`, `test_database_integrity_guards.py`, `test_used_drug_integrity.py` e `test_request_identity_integrity.py`. | Fluxos futuros de validação, cancelamento/adendo devem preservar a mesma política sem criar atalhos de lifecycle. |
| **RF-RX-05 — Interações medicamentosas** | **Gate clínico** | `Interaction` possui versão, procedência, aprovação e estado ativo. `0005_approved_reference_integrity.py` congela conteúdo/metadados depois da aprovação, permite somente desativação e impede reativação/exclusão da mesma versão; `test_reference_governance_integrity.py` cobre aplicação, bulk update e SQL direto. | T-RX-02 e T-RX-08: referência clínica real aprovada e mecanismo de avaliação sem lógica clínica hardcoded. |
| **RF-RX-06 — Alergias** | **Gate clínico** | `MedicationSafetyReview.AllergyStatus` possui `UNAVAILABLE`/revisão manual/estruturada para representar ausência de fonte sem falso negativo. | T-RX-03 e T-RX-09: extensão PEP `AllergyIntolerance` e tela/serviço de revisão humana. |
| **RF-RX-07 — Dose por idade/peso** | **Gate clínico** | `DoseRule` possui procedência/aprovação; `DoseStatus.NOT_EVALUABLE` está modelado. Referências aprovadas recebem a mesma proteção imutável de `0005_approved_reference_integrity.py`, sem fórmula executável ou conteúdo clínico real embutido. | T-RX-02/T-RX-08: referência real governada e fonte estruturada aprovada de peso; nenhum cálculo automático deve ser habilitado antes disso. |
| **RF-RX-08 — Validação farmacêutica** | **Pendente** | Entidades append-only `MedicationSafetyReview`/`MedicationSafetyFinding`, permissões e eventos previstos já possuem fundação. | T-RX-09: decisão explícita por farmacêutico, UI e serviço; sem autoaprovação e sem confundir com assinatura jurídica. |
| **RF-RX-09 — Estoque farmacêutico** | **Implementado** | `StockItem`, `Lot`, `StockMovement`; `stock_services.py`; `/estoque-farmacia/`; `tests/test_stock.py`; E2E/a11y atual. `0007_stock_identity_guards.py` impede reescrever medicamento/localização de estoque depois da existência de lotes e identidade de lote depois do primeiro movimento, sem bloquear `quantity_available`; `test_stock_identity_db_guards.py` cobre bypass por bulk/SQL e os casos ainda editáveis. | Dispensação ainda não consome o estoque porque T-RX-11 está pendente. |
| **RF-RX-10 — Dispensação transacional** | **Parcial** | Primitivas de saldo usam `transaction.atomic()` + `select_for_update()`; T-RX-13 prova concorrência do último saldo no PostgreSQL. Modelos de dispensação e `operation_key` existem. | T-RX-11: serviço de dispensação idempotente ligando `MedicationDispenseItem` + `StockMovement` na mesma transação. |
| **RF-RX-11 — Rastreabilidade por lote** | **Parcial** | FKs `MedicationDispenseItem -> request_item/lot` e `StockMovement -> dispense_item` já modelam a cadeia; proteção append-only existe em aplicação/PostgreSQL e a identidade do lote após movimentação é protegida por `0007_stock_identity_guards.py`. | T-RX-11: criar o fluxo operacional que persiste essa cadeia na dispensação real. |
| **RF-RX-12 — Autorização** | **Implementado** | `permissions.py` e selectors aplicam RBAC+ABAC deny-by-default; `tests/test_permissions.py`/`test_selectors.py`. Catálogo/estoque usam permissões explícitas. | Futuras views de prescrição/validação/dispensação devem reutilizar as mesmas fronteiras e ganhar E2E de negação. |
| **RF-RX-13 — Auditoria e eventos** | **Parcial** | `events.py` emite payload técnico pós-commit; `prescription.created` e `stock.low` ativos; acesso a estoque/lotes gera audit ACCESS; `tests/test_audit_events.py`; contrato `contracts/events.asyncapi.yaml`. | T-RX-12: `prescription.validated` e `medication.dispensed`, além de leitura/escrita das futuras telas. |
| **RF-RX-14 — PWA network-only** | **Parcial** | `tests/test_architecture.py` proíbe API REST/cache/fila offline RX; `tests/e2e/prescription_pwa_boundary.spec.js` comprova em runtime que catálogo/estoque não entram em Cache Storage/IndexedDB e usam fallback genérico offline. | T-RX-16: repetir a prova E2E nas futuras mutações de prescrição e dispensação. |

## Requisitos não funcionais

| Requisito | Estado | Evidência / observação |
|---|---|---|
| **RNF-RX-01 — PostgreSQL como fonte de verdade** | **Implementado** | CI aplica migrations e executa testes contra PostgreSQL. As migrations `0004`–`0008` levam invariantes críticas de append-only, referências aprovadas, medicamento prescrito, identidade de estoque/lote e identidade da prescrição para o banco real; suítes específicas tentam bypass por `QuerySet.update()` e SQL direto. SQLite permanece somente como conveniência de desenvolvimento DEBUG. |
| **RNF-RX-02 — Mutação de estoque atômica/concorrente** | **Implementado para estoque; dispensação pendente** | `stock_services.py` e `tests/test_stock_concurrency.py` comprovam lock e saldo não negativo. `0007_stock_identity_guards.py` preserva identidade sem bloquear a atualização transacional de `quantity_available`. T-RX-11 ainda precisa compor a dispensação final. |
| **RNF-RX-03 — Sem REST público** | **Implementado** | `tests/test_architecture.py` inspeciona o URLConf RX e impede rotas `api/`; interação atual é server-rendered. |
| **RNF-RX-04 — Minimização de PHI em logs/eventos** | **Parcial** | Eventos atuais têm allowlist técnico; campos textuais sensíveis são excluídos do auditlog onde aplicável; `tests/test_audit_events.py`. Fluxos futuros ainda precisam da mesma verificação. |
| **RNF-RX-05 — WCAG 2.1 AA / responsivo** | **Parcial** | `tests/e2e/prescription_accessibility.spec.js` executa axe em catálogo/estoque e valida 390×844 e 768×1024. Prescrição/validação/dispensação ainda não possuem telas. |
| **RNF-RX-06 — Referências governadas** | **Parcial / gate clínico** | Estrutura de procedência, versão e aprovação existe e referências começam inativas. `0005_approved_reference_integrity.py` torna versões aprovadas imutáveis inclusive contra bulk update/SQL, permite desativação e exige nova versão para voltar ao uso. T-RX-02 ainda precisa validar a fonte/conteúdo real. |
| **RNF-RX-07 — Migrations reversíveis** | **Implementado na fundação atual** | Migrations da app são versionadas; `0004_database_mutation_guards.py` a `0008_request_history_guards.py` possuem operações reversas explícitas e são no-op fora de PostgreSQL quando o guard é específico do banco. |
| **RNF-RX-08 — Idempotência/conflito seguro de dispensação** | **Parcial** | Estoque já possui idempotência por chave e conflitos seguros; concorrência foi provada em T-RX-13. A idempotência da dispensação completa depende de T-RX-11. |

## Superfícies efetivamente publicadas

As únicas rotas RX publicadas atualmente em `apps/clinical/prescription/urls.py` são:

- `/medicamentos/`;
- `/medicamentos/novo/`;
- `/medicamentos/<uuid>/editar/`;
- `/estoque-farmacia/`.

As telas de lista/detalhe/criação de prescrição, validação farmacêutica e dispensação descritas em `spec.md` continuam **planejadas**, não publicadas.

## Evidências automatizadas principais

- Catálogo/governança: `apps/clinical/prescription/tests/test_catalog.py`, `test_reference_governance_integrity.py`, `test_used_drug_integrity.py`.
- Modelos/invariantes: `test_models.py`, `test_append_only_integrity.py`, `test_request_history_integrity.py`, `test_database_integrity_guards.py`, `test_request_identity_integrity.py`.
- Prescrição DRAFT/SUBMITTED: `test_services.py`.
- RBAC/ABAC: `test_permissions.py`, `test_selectors.py`.
- Estoque/ledger: `test_stock.py`, `test_stock_identity_db_guards.py`.
- Concorrência PostgreSQL: `test_stock_concurrency.py`.
- Auditoria/eventos: `test_audit_events.py`.
- Arquitetura/no-public-API/no-offline: `test_architecture.py`.
- Acessibilidade/responsividade: `tests/e2e/prescription_accessibility.spec.js`.
- Boundary PWA runtime: `tests/e2e/prescription_pwa_boundary.spec.js`.

## Gates que impedem o fechamento da Spec 003

A rastreabilidade final só pode ser marcada como concluída depois de:

1. T-RX-02 — governança clínica/farmacêutica de referências reais;
2. T-RX-03 — fonte estruturada aprovada de alergias;
3. T-RX-08/T-RX-09 — checagem e validação farmacêutica com decisão humana explícita;
4. T-RX-11/T-RX-12 — dispensação + auditoria/eventos completos;
5. T-RX-14/T-RX-15/T-RX-16 — jornadas clínicas, acessibilidade e network-only das superfícies finais;
6. confirmar a integração com Spec 004/009 sem duplicar a fonte de verdade clínica ou de estoque.

Até esses gates serem atendidos, **T-RX-17 permanece aberta**. Esta baseline existe para impedir que fundações de modelo/serviço sejam confundidas com jornadas clínicas prontas para uso.
