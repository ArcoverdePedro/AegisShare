# Evidências locais — Spec 009 v1

Executadas em 2026-09-18, com dados sintéticos. O usuário autorizou o recorte respondendo “[@Ponytail] continue com o SDD” à pergunta de aprovação da proposta de catálogo/requisições.

## Resultados executados

- **507 testes passaram no PostgreSQL 18**, incluindo os quatro casos concorrentes de inventory. Suíte completa: `/tmp/inventory-postgres.log`, 76,251 s.
- SQLite: **dez testes de workflow passaram**, quatro concorrentes corretamente ignorados nesse banco. `/tmp/inventory-sqlite.log`.
- **Cinco jornadas Playwright passaram na execução final, sem retries**, 13,5 s. `/tmp/inventory-e2e-final.log`: registrar/alterar catálogo/retry/snapshot; consulta institucional/leitor/cliente; offline; telefone/tablet/axe; revogar capacidade via Admin com formulário aberto e confirmar POST 403/consulta 200.
- Nas execuções anteriores, seletores do teste de Admin falharam: checkbox sem dois-pontos, UUID do usuário e botão de remoção com ID atual. Corrigidos os testes/fixture, sem mudança nas regras do produto; todas as jornadas foram repetidas. Logs anteriores: `/tmp/inventory-e2e.log` e `/tmp/inventory-e2e-second.log`.
- Migration inventory.0001_initial aplicada, revertida e reaplicada em SQLite descartável. `/tmp/inventory-rollback.log`. Aplicada também nos bancos PostgreSQL de teste.
- Ruff em todo o repositório: passou. Removidas cinco anotações `noqa: E402` desnecessárias somente no import de django das fixtures antigas; imports posteriores a django.setup preservam suas anotações necessárias. Format dos arquivos novos: passou.
- Django check: sem problemas; makemigrations --check --dry-run: sem alterações pendentes.
- Bandit: sem achados no app inventory. pip-audit sobre site-packages do ambiente atual: sem vulnerabilidades conhecidas. Ferramentas executadas em ambiente temporário, sem novas dependências da aplicação. `/tmp/inventory-bandit.log`, `/tmp/inventory-audit.log`.
- Logs de suíte/servidores inspecionados: sem marcadores sintéticos de código/nome de material usados no teste. Auditlog minimizado verificado no teste específico.
- agent-browser: login/formulário autenticado renderizados, sem erros de JavaScript registrados. Inspeção visual da requisição em 390 × 844: legível, controles e aviso visíveis. `/tmp/inventory-form.png`, `/tmp/inventory-mobile.png`.
- Lighthouse: **página inicial não autenticada**, uma execução em http://127.0.0.1:8771/. Desempenho **73**, acessibilidade **98**, boas práticas **100**, SEO **90**. Aviso: desempenho inferior à meta 90; a meta não foi atingida. Token GitHub não configurado. Relatórios `/tmp/inventory-lighthouse/`. Não é medição autenticada das telas inventory ou certificação PWA.

A suíte PostgreSQL cobre a implementação final; depois foram alterados somente comentário de limite do select, fixtures/seletores E2E, anotações de lint sem efeito em runtime e documentação. Não há execução remota de CI, deployment ou validação institucional declarados.

## Rastreabilidade executável

Workflow: `apps/admin/inventory/tests/test_workflow.py`. Concorrência: `apps/admin/inventory/tests/test_concurrency.py`. Browser: `tests/e2e/inventory_journeys.spec.js`.

| Critério | Evidência |
|---|---|
| CA-INV-01 | test_catalog_validation_admin_and_append_only_protection; test_snapshot_retry_inactive_and_new_key; jornada de catálogo/Admin |
| CA-INV-02 | test_institutional_read_and_capability_revocation; test_internal_role_and_both_capabilities_required; jornadas leitor/cliente e revogação real |
| CA-INV-03 | test_invalid_input_preserves_key_and_internal_validation; test_snapshot_retry_inactive_and_new_key; confirmação/limites/snapshot do servidor |
| CA-INV-04 | test_conflicts_do_not_reveal_original; test_snapshot_retry_inactive_and_new_key; quatro testes PostgreSQL: retry único, colisão entre itens, quantidades incompatíveis, chaves novas distintas |
| CA-INV-05 | test_pagination_audits_only_page_and_no_related_n_plus_one; 26 registros/página 25/ACCESS apenas página e consultas relacionadas limitadas |
| CA-INV-06 | test_audit_failure_rolls_back_and_blocks_reads_and_retries; test_minimized_audit_and_exact_rendered_form_choices; test_catalog_validation_admin_and_append_only_protection |
| CA-INV-07 | test_privacy_headers_csrf_methods_missing_and_redirects; jornadas offline/telefone 390 × 844/tablet 768 × 1024 com axe sem violações sérias/críticas e sem overflow |

## Limites preservados

Dois modelos, Admin nativo apenas do catálogo, Forms e quatro FBVs. Sem saldo, medicamentos, compra, reserva ou entrega confirmada; sem eventos sem consumidor. Consulta institucional de todos os registros por capacidade explícita. Sem dependência nova ou JS próprio. Seletor nativo carrega catálogo ativo inteiro; limite documentado para extensão com busca paginada quando necessário.

PROTECT e guardas append-only protegem entradas da aplicação, sem alegação de imutabilidade contra SQL/ORM direto. Validação institucional e meta Lighthouse continuam pendentes. [Guia operacional](../../docs/estoque-requisicoes.md).
