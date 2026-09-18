# Evidências locais — Spec 008

Executadas em 2026-09-18, com dados sintéticos. Recorte autorizado pelo usuário com “[@Ponytail] continue”, em resposta à pergunta de aprovação da preparação manual de contas.

## Resultados

- Suíte completa no PostgreSQL 18: **493 testes passaram**. Log local `/tmp/billing-postgres.log`.
- Após o ajuste final de auditoria do redirecionamento e navegação: **17 testes billing passaram no PostgreSQL**, incluindo cinco casos concorrentes. `/tmp/billing-final-pg.log`.
- SQLite: **12 testes de workflow passaram**. `/tmp/billing-tests.log`. Concorrência real foi validada no PostgreSQL.
- Playwright final: **cinco jornadas passaram**, sem retries. `/tmp/billing-e2e-final.log`: abertura/item/total/retry; usuário fora do PEP; offline sem fila/cache; telefone/tablet com axe sem violações sérias/críticas e sem overflow; revogação efetiva pelo Admin com formulário aberto.
- Migration aplicada, revertida e reaplicada em SQLite descartável: sucesso. `/tmp/billing-rollback.log`. Migration inicial também aplicada nos bancos PostgreSQL de testes.
- Ruff check e format: passaram. Django check e ausência de migrations pendentes: passaram.
- Bandit: sem achados no app billing. pip-audit: sem vulnerabilidades conhecidas. `/tmp/billing-bandit.log`, `/tmp/billing-audit.log`.
- Inspeção de logs de teste/servidor: sem marcadores sintéticos de paciente, descrição ou valor usados nas jornadas.
- Inspeção visual do detalhe em 390 × 844: total 0,50, cards legíveis, navegação e aviso de preparação. Captura local `/tmp/billing-mobile.png`.
- Lighthouse: uma execução na **página inicial**, não medição autenticada de faturamento. Desempenho **73**, acessibilidade **98**, boas práticas **100**, SEO **90**. Aviso: desempenho abaixo da meta 90; meta não atingida. Token GitHub ausente. Relatórios em `/tmp/billing-lighthouse/`.

A suíte completa foi executada antes dos dois ajustes finais; os testes específicos PostgreSQL e as cinco jornadas foram repetidos depois. Não se declara execução remota de CI, deployment, certificação ou validação institucional.

## Rastreabilidade

Testes HTTP em `apps/admin/billing/tests/test_workflow.py`, concorrência em `test_concurrency.py`, jornadas em `tests/e2e/billing_journeys.spec.js`.

| Aceitação | Evidência executável |
|---|---|
| CA-BILL-01 | `test_open_after_closure_retry_and_single_account`, `test_open_confirmation_is_required`; jornada de abertura |
| CA-BILL-02 | `test_scope_revocation_and_inactive_patient`, `test_capabilities_internal_role_and_admin_without_capability`; jornadas de outsider e revogação Admin |
| CA-BILL-03 | `test_exact_decimal_and_maximum_total_without_integer_overflow`, `test_invalid_values_and_missing_confirmation_preserve_key`; total 0.10 × 3 + 0.20 = 0.50 e dez itens máximos em ambos os bancos |
| CA-BILL-04 | `test_item_retry_normalizes_decimal_and_trim_and_new_key_is_distinct`, `test_conflicting_actor_and_other_account_key_do_not_reveal_original`; cinco testes concorrentes de retries, chaves distintas e colisões entre agregados |
| CA-BILL-05 | `test_item_pagination_total_all_rows_and_bounded_queries`; 26 itens, página com 25, total de todos, queries limitadas |
| CA-BILL-06 | `test_audit_failure_rolls_back_account_item_and_blocks_reads`, `test_append_only_protection_and_minimized_audit`; rollback, leitura bloqueada e ACCESS antes do redirect |
| CA-BILL-07 | `test_privacy_headers_errors_redirects_csrf_and_methods`; jornadas offline/mobile/tablet/axe e verificações acima |

## Simplicidade e limites

Reuso de PEP, usuário, auditlog, layout e middleware; Forms/FBVs/ORM nativos. PostgreSQL soma numérica exata; SQLite usa agregado nativo de centavos inteiros, com estado mínimo exigido pela API, evitando perda de centavos e overflow. Sem carregar todos os itens ou persistir totais redundantes.

Sem dependência nova, JS próprio, service class ou Admin financeiro. Proteção append-only nas entradas da aplicação e FKs PROTECT; não é imutabilidade contra SQL/ORM direto. Cobrança, fechamento, correções, tarifas e guias exigem contratos posteriores. Uso real depende de validação institucional.
