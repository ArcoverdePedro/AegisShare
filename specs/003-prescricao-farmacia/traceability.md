# Rastreabilidade — Spec 003 Prescrição e Farmácia

> Baseline consolidada em 2026-09-15 após a implementação das superfícies clínicas de prescrição, validação e dispensação.  
> Esta matriz separa **implementação técnica** de **conteúdo clínico governado**: uma engine pronta não autoriza carregar referências terapêuticas reais sem T-RX-02.

## Legenda

- **Implementado** — requisito entregue na superfície atual e coberto por testes automatizados.
- **Implementado / gate clínico** — mecanismo técnico entregue, mas conteúdo/fonte clínica real continua bloqueado por governança externa.
- **Gate externo** — depende de validação/decisão que não pode ser substituída por código.

## Requisitos funcionais

| Requisito | Estado | Implementação / evidência | Gate restante |
|---|---|---|---|
| **RF-RX-01 — Catálogo de medicamentos** | **Implementado** | `Drug`, `catalog_services.py`, `DrugForm`, catálogo/criação/edição server-rendered, auditoria e testes de integridade histórica. | Conteúdo clínico real de referências continua subordinado a T-RX-02. |
| **RF-RX-02 — Prescrição vinculada ao PEP** | **Implementado** | `MedicationRequest` referencia `Encounter` canônico; `create_medication_request()` revalida encontro/PEP; rotas `/prescricoes/`, `/prescricoes/nova/` e detalhe estão publicadas. | Nenhum para o fluxo técnico atual. |
| **RF-RX-03 — Itens estruturados** | **Implementado** | `MedicationRequestItem`, formset server-side e services validam medicamento, dose, unidade, via, frequência, duração e ordem. | Terminologias clínicas oficiais permanecem governadas fora do código. |
| **RF-RX-04 — Histórico imutável** | **Implementado** | Services, signals e guards PostgreSQL impedem edição/exclusão destrutiva após DRAFT; substituição/cancelamento preservam histórico. | Nenhum para a superfície atual. |
| **RF-RX-05 — Interações medicamentosas** | **Implementado / gate clínico** | `Interaction` possui procedência/versão/aprovação; `safety.py` considera somente referências ativas/aprovadas e respeita `blocking` como dado governado. Testes usam interação sintética bloqueante. | **T-RX-02:** base real, severidade e bloqueio precisam de aprovação clínica/farmacêutica. |
| **RF-RX-06 — Alergias** | **Implementado / gate clínico** | Validação farmacêutica usa `UNAVAILABLE`/revisão manual explícita e nunca infere “sem alergias conhecidas”. Extensão PEP `AllergyIntolerance` está especificada em `specs/001-pep/extensions/allergy-intolerance/`. | T-ALLERGY-02–05: validar modelo/terminologia e implementar fonte estruturada antes de automação. |
| **RF-RX-07 — Dose por idade/peso** | **Implementado / gate clínico** | `DoseRule` governada + safety engine determinístico; idade vem do PEP; regra dependente de peso/fato ausente resulta em `NOT_EVALUABLE`, sem estimativa. | **T-RX-02** para regras reais e futura fonte estruturada aprovada de peso. |
| **RF-RX-08 — Validação farmacêutica** | **Implementado** | `/prescricoes/<uuid>/validar/`, `validate_medication_request()`, `MedicationSafetyReview`/findings append-only, gate manual de alergias, bloqueio seguro e evento `prescription.validated`. | Assinatura jurídica permanece separada em T-PEP-08. |
| **RF-RX-09 — Estoque farmacêutico** | **Implementado** | `StockItem`, `Lot`, `StockMovement`, services de entrada/ajuste, `/estoque-farmacia/`, validade/saldo e `stock.low`. | Integração futura com estoque geral da Spec 009. |
| **RF-RX-10 — Dispensação transacional** | **Implementado** | `dispense_medication()` usa `transaction.atomic()`, `select_for_update()`, `operation_key` idempotente, valida lote/saldo e baixa estoque na mesma transação. | Políticas futuras de fracionamento/devolução não fazem parte desta entrega. |
| **RF-RX-11 — Rastreabilidade por lote** | **Implementado** | `MedicationDispense -> MedicationDispenseItem -> Lot -> StockMovement` preserva cadeia prescrição/encontro/lote; registros concluídos são append-only. | Nenhum para o fluxo atual. |
| **RF-RX-12 — Autorização** | **Implementado** | `permissions.py`, selectors e views aplicam RBAC + `can_access_patient()` deny-by-default. Gherkin/Playwright cobrem negação `CLI`, e objetos fora do escopo não revelam PHI. | Nenhum para as rotas publicadas. |
| **RF-RX-13 — Auditoria e eventos** | **Implementado** | Leituras identificáveis geram `ACCESS`; mutações críticas usam ator explícito; AsyncAPI cobre `prescription.created`, `prescription.validated`, `medication.dispensed` e `stock.low`, todos pós-commit e sem PHI textual. | Nenhum para os eventos atuais. |
| **RF-RX-14 — PWA network-only** | **Implementado** | Arquitetura e E2E provam ausência de nova API REST pública, `private/no-store`, nenhuma persistência RX em Cache Storage/IndexedDB e falha de POST clínico offline sem fila local. | Qualquer sincronização offline futura exige contrato clínico específico aprovado. |

## Requisitos não funcionais

| Requisito | Estado | Evidência / observação |
|---|---|---|
| **RNF-RX-01 — PostgreSQL como fonte de verdade** | **Implementado** | CI aplica migrations e testes no PostgreSQL; guards/constraints protegem invariantes críticas também contra bypass de aplicação. |
| **RNF-RX-02 — Estoque atômico/concorrente** | **Implementado** | Services usam transações/locks e `test_stock_concurrency.py` disputa o último saldo com conexões independentes. |
| **RNF-RX-03 — Sem REST público** | **Implementado** | `test_architecture.py` inspeciona URLConf e proíbe novas rotas `api/`; toda a nova superfície é Django server-rendered. |
| **RNF-RX-04 — Minimização de PHI** | **Implementado** | campos textuais sensíveis são excluídos do auditlog; eventos usam allowlist técnico; negações não criam falso `ACCESS`. |
| **RNF-RX-05 — WCAG 2.1 AA / responsivo** | **Implementado** | `tests/e2e/prescription_accessibility.spec.js` executa axe-core e valida overflow em 390×844 e 768×1024 para catálogo, estoque, prescrição, validação e dispensação. |
| **RNF-RX-06 — Referências governadas** | **Implementado / gate clínico** | estrutura de procedência, versão, aprovação, imutabilidade e desativação está implementada. | T-RX-02 precisa aprovar fontes/conteúdo reais. |
| **RNF-RX-07 — Migrations reversíveis** | **Implementado** | migrations RX são versionadas e guards específicos de PostgreSQL possuem caminho reverso/no-op controlado fora do banco-alvo. |
| **RNF-RX-08 — Idempotência/conflito seguro** | **Implementado** | dispensação usa `operation_key` única; replay idêntico retorna a operação existente e replay divergente é rejeitado; saldo insuficiente gera erro operacional seguro. |

## Superfícies efetivamente publicadas

`apps/clinical/prescription/urls.py` publica atualmente:

- `GET /prescricoes/` — lista autorizada;
- `GET|POST /prescricoes/nova/` — criação de rascunho + itens;
- `GET /prescricoes/<uuid>/` — detalhe/histórico;
- `POST /prescricoes/<uuid>/submeter/` — submissão;
- `GET|POST /prescricoes/<uuid>/validar/` — revisão/validação farmacêutica;
- `POST /prescricoes/<uuid>/cancelar/` — cancelamento sem apagar histórico;
- `GET|POST /prescricoes/<uuid>/dispensar/` — dispensação por lote;
- `GET /dispensacoes/` e `GET /dispensacoes/<uuid>/` — histórico de dispensações;
- `GET /medicamentos/`, `GET|POST /medicamentos/novo/`, `GET|POST /medicamentos/<uuid>/editar/` — catálogo;
- `GET /estoque-farmacia/` — estoque/lotes.

Nenhuma rota nova usa `/api/`.

## Evidências automatizadas principais

- **Catálogo/governança:** `test_catalog.py`, `test_catalog_csrf.py`, `test_reference_governance_integrity.py`, `test_used_drug_integrity.py`.
- **Lifecycle/histórico:** `test_services.py`, `test_request_history_integrity.py`, `test_append_only_integrity.py`, `test_database_integrity_guards.py`, `test_request_identity_integrity.py`.
- **Safety/validação/dispensação:** `test_safety_and_dispense.py` e testes de auditoria/eventos da app RX.
- **Concorrência PostgreSQL:** `test_stock_concurrency.py`.
- **Autorização/negação:** `test_permissions.py`, `test_selectors.py`, `test_anonymous_boundary.py`, `test_denied_access_audit.py`, `features/authorization.feature`, `tests/e2e/prescription_authorization.spec.js`.
- **Aceitação clínica:** `features/clinical_flows.feature`, `tests/e2e/prescription_clinical_flows.spec.js`, `test_acceptance_traceability.py`.
- **Auditoria/AsyncAPI:** `test_event_contract.py`, `test_audit_events.py`, `test_auditlog_sensitive_fields.py`, `test_prescription_audit_actor.py`, testes de ator do fluxo clínico/estoque.
- **Cache/PWA:** `test_architecture.py`, `test_response_cache_policy.py`, `tests/e2e/prescription_pwa_boundary.spec.js`.
- **Acessibilidade/responsividade:** `tests/e2e/prescription_accessibility.spec.js`.

## Gates que permanecem deliberadamente abertos

1. **T-RX-02 — governança clínica/farmacêutica:** nenhuma referência terapêutica real deve entrar no runtime antes da aprovação de fonte, versão e conteúdo.
2. **Extensão PEP AllergyIntolerance:** o contrato está definido, mas sua implementação foi explicitamente bloqueada até validação clínica dos estados/terminologia; o fallback manual RX continua obrigatório.
3. **Fonte estruturada de peso:** regras dependentes de peso permanecem `NOT_EVALUABLE` até uma spec clínica aprovada fornecer esse fato.
4. **T-PEP-08 — assinatura jurídica/operacional:** não é substituída pela validação farmacêutica.
5. **T-RX-17 — integrações 004/009:** deve ser fechada somente quando essas specs fornecerem suas fontes/ownership sem duplicação de verdade.

## Estado de Definition of Done

A **superfície técnica atual** da Spec 003 está implementada e possui rastreabilidade código → contrato → testes. O fechamento global da spec permanece condicionado aos gates externos acima; estes não devem ser marcados como concluídos por conveniência de backlog.
