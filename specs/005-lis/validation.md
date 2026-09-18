# Evidências — LIS v1

Data: 2026-09-17. Aprovação: “aprovado, implemente”.

## Entrega

App `apps.clinical.lis`, três modelos, migration inicial, catálogo no Admin e quatro FBVs. Pedidos preservam o retrato do exame; coleta é única por pedido. Locks de encontro/pedido, constraints, chaves de operação e transações preservam consistência e auditlog. Sem dependências novas, API pública, canais, workers ou JavaScript de aplicação.

## Gates locais

| Verificação | Resultado |
|---|---|
| Suíte completa PostgreSQL 18 descartável | **433 testes passaram, sem pulados** |
| Testes LIS | 12 testes HTTP/domínio e 2 concorrentes no PostgreSQL |
| Regressão após ajuste final das opções de catálogo no formulário | 14 testes em SQLite: OK, 2 concorrentes pulados por ausência de lock de linha |
| Playwright / Chromium | **4 jornadas passaram**, sem retries |
| Mobile/axe | Lista, pedido, detalhe e coleta em 390×844 e 768×1024: sem overflow nem violações sérias/críticas |
| Offline | Sem confirmação de pedido; fallback offline; sem novas linhas em IndexedDB, sem rotas/conteúdo LIS no cache |
| Migration em SQLite descartável | Aplicar → zero → reaplicar: passou |
| Ruff e format dos novos arquivos | Passaram |
| Django check / makemigrations --check --dry-run | Sem problemas / sem alterações pendentes |
| Bandit do novo módulo, excluindo testes | Sem achados |
| pip-audit no ambiente instalado | Nenhuma vulnerabilidade conhecida encontrada |
| Lighthouse CI na página inicial local | Obrigatórios passaram: acessibilidade 98, boas práticas 100; SEO 90; desempenho 73 como aviso |
| compileall, sintaxe JS, git diff --check | Passaram |

A preparação `tests/e2e/prepare_lis_journeys.py` foi adicionada ao workflow existente. Credenciais dessa fixture são públicas e limitadas a ambiente de teste.

## Rastreabilidade executável

| Critério | Testes |
|---|---|
| CA-LIS-01 | `test_order_and_collection_preserve_snapshot_actor_and_history`, `test_inactive_test_cannot_create_new_order`; jornada CA-01/02/05 |
| CA-LIS-02 | `test_invalid_time_and_missing_confirmation_do_not_write`, `test_sample_code_is_unique_and_error_does_not_identify_other_order` |
| CA-LIS-03 | `test_foreign_patient_and_revoked_grant_are_hidden`, `test_capabilities_and_internal_role_are_required`, `test_closed_encounter_prevents_order_and_collection`; jornada CA-03 |
| CA-LIS-04 | `test_pagination_filters_and_bounded_related_queries`, teste de retrato preservado; jornada CA-04/07 |
| CA-LIS-05 | `test_conflicting_key_or_collection_does_not_overwrite`, `test_concurrent_identical_order_returns_same_record`, `test_two_distinct_collections_produce_one_record_and_conflict` |
| CA-LIS-06 | `test_audit_failure_rolls_back_order_and_specimen`, `test_audit_omits_sensitive_text_and_records_reads` |
| CA-LIS-07 | `test_headers_include_denial_csrf_and_invalid_methods`; jornadas offline e mobile/axe |

Testes em `apps/clinical/lis/tests/` e `tests/e2e/lis_journeys.spec.js`. Os cenários Gherkin servem como contrato, sem runner BDD adicional.

## Limites

CI remoto, Trivy, stack Compose completa/Redis e deploy não foram executados. Lighthouse avalia a página inicial; não afirma categoria numérica PWA. A implementação de histórico append-only é na aplicação, sem proteção contra administrador direto do banco.

Nenhum banco de produção foi migrado, grupo recebeu permissão automaticamente ou exame clínico foi pré-carregado. Uso real depende da instituição, incluindo catálogo, identidade física da amostra e fluxos de exceção/correção. Ingestão HL7/ASTM e resultados permanecem fora desta entrega.

Guia: [laboratorio.md](../../docs/laboratorio.md).
