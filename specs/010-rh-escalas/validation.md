# Evidências — Spec 010 v1

Recorte autorizado e implementado em 2026-09-28. Verificação final repetida em 2026-10-02.

## Rastreabilidade

| Critério | Evidência executável |
|---|---|
| CA-HR-01 | `EmployeeTests.test_model_validation_trim_unique_protect_and_no_delete`, `EmployeeConcurrencyTests.test_parallel_creation_keeps_one_profile` |
| CA-HR-02 | `test_admin_create_uses_only_eligible_unlinked_users`, `test_admin_edit_cannot_replace_user_or_delete`, jornada Playwright de criação/edição/revogação |
| CA-HR-03 | `test_profile_status_is_independent_and_history_remains_visible`, `test_admin_edit_cannot_replace_user_or_delete` |
| CA-HR-04 | `test_permissions_roles_and_revocation`, jornadas Playwright de consulta e revogação |
| CA-HR-05 | `test_pagination_audits_only_visible_records_without_n_plus_one`, jornada Playwright responsiva |
| CA-HR-06 | `test_read_audit_failure_blocks_personal_content`, `test_admin_audit_failures_roll_back_create_and_update`, `test_audit_minimizes_identity_and_functional_text` |
| CA-HR-07 | `test_privacy_headers_csrf_methods_missing_and_redirects`, jornadas Playwright offline/mobile/tablet/axe |

## Resultados locais

- Suíte Django completa em PostgreSQL: 518 testes aprovados antes da atualização transitiva de `anyio`; testes do app repetidos depois da atualização.
- App RH em SQLite: 10 aprovados e 1 teste concorrente corretamente ignorado por depender de PostgreSQL.
- Uma repetição da suíte completa em SQLite em 2026-10-02 foi interrompida após ficar sem saída; não foi contabilizada como aprovação.
- Playwright: 5 jornadas aprovadas, incluindo criação/edição, capacidade global, offline sem persistência, telefone/tablet/axe e revogação com formulário aberto.
- Migration: aplicar, reverter e reaplicar `hr.0001_initial` em banco descartável.
- Ruff, formatação, `manage.py check`, `makemigrations --check` e `git diff --check`: aprovados.
- Bandit no app RH: nenhum achado.
- `pip-audit`: os alertas CVE-2026-63374 e CVE-2026-64847 levaram `anyio` de 4.11.0 a 4.15.1; nova execução sem vulnerabilidades conhecidas.
- Lighthouse na raiz sem sessão: performance 72, acessibilidade 98, boas práticas 100 e SEO 90. A meta de performance 90 não foi atingida; a medição não representa a rota RH autenticada.
- Inspeção de detalhe em viewport 390 × 844: sem overflow visual observado.

O pipeline remoto, o deploy e a validação institucional não foram executados localmente. Dados reais permanecem bloqueados até validação de finalidade, acesso, conteúdo dos campos e aceitação da fronteira de auditoria do Admin.
