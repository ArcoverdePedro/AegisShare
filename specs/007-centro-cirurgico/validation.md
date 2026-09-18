# Evidências locais — Centro Cirúrgico v1 — 2026-09-18

Autorização: resposta “[@Ponytail] continue” à pergunta de aprovação do recorte apresentado da Spec 007. Implementação técnica para piloto sintético; validação institucional para uso real permanece separada.

| Verificação | Resultado |
|---|---|
| Suíte completa Django / PostgreSQL 18 | 476 testes, todos passaram; inclui concorrência surgery e regressões dos módulos existentes |
| Surgery / SQLite | 13 testes: 11 passaram e 2 de concorrência foram pulados; estes passaram no PostgreSQL |
| Ruff check / format | Passaram nos arquivos Python do módulo, fixture e configuração alterada |
| Django check / makemigrations --check --dry-run | Sem problemas / sem alterações |
| Migration SQLite descartável | Aplicar surgery.0001, reverter para zero e reaplicar: OK |
| Playwright Chromium, sem retries | 5 jornadas passaram: criação/retry, isolamento PEP, offline, mobile/axe e revogação real pelo Admin após abrir formulário |
| Telefone/tablet | Lista/form/detalhe em 390×844 e 768×1024 sem overflow horizontal nem violações axe sérias/críticas WCAG |
| Offline | Sem confirmação, nomes/contagens IndexedDB inalterados, sem páginas /cirurgias/ ou conteúdo sintético no Cache Storage; nome sintético ausente de localStorage/sessionStorage |
| Inspeção visual | Formulário de solicitação em telefone conferido; aviso de ausência de agendamento/autorização e campos renderizados |
| Logs sintéticos | Nome de paciente/procedimento e código privado ausentes dos logs do servidor e da suíte PostgreSQL |
| Bandit / pip-audit | Sem findings no app (testes excluídos) / sem vulnerabilidades conhecidas nas dependências instaladas |
| Lighthouse da raiz pública local | Acessibilidade 0,98; boas práticas 1,00; SEO 0,90; desempenho 0,73, aviso abaixo da meta 0,90. Gates de erro passaram |

Não houve CI remoto ou deployment. Lighthouse público não substitui a jornada autenticada, verificada por Playwright/axe. Dados, contas, chaves e bancos de teste são sintéticos. Sem nova dependência de aplicação ou JS próprio. A meta de desempenho Lighthouse ainda não foi atingida.

## Rastreabilidade executável

Testes Python abaixo em `apps/clinical/surgery/tests/test_workflow.py`, salvo indicação explícita. Gherkin documenta aceitação; Django e Playwright são executáveis.

| Critério / requisito | Superfície | Testes |
|---|---|---|
| CA-01 / RF-01/02 | Admin Procedure; case_create / case_form | test_snapshot_retry_and_new_operation; test_append_only_protect_and_catalog_validation; E2E solicitação/retry |
| CA-02 / RF-03/04 | capacidades/escopo em todas as FBVs | test_capabilities_and_internal_role_are_required; test_revocation_and_inactive_patient_hide_history; E2E isolamento e revogação pelo Admin |
| CA-03 / RF-04 | request_procedure e case_create | test_closed_encounter_blocks_new_and_retry_but_preserves_read |
| CA-04 / RF-05/08 | case_list/detail e templates | test_pagination_audits_only_visible_records_without_n_plus_one; test_audit_minimizes_content_and_records_actor |
| CA-05 / RF-06/07 | locks, constraint e snapshot | test_snapshot_retry_and_new_operation; test_conflicting_key_does_not_reveal_original; tests/test_concurrency.py: retry idêntico e colisão entre encontros reais no PostgreSQL |
| CA-06 / RF-07/08 | transação, auditlog e falha segura de leitura | test_audit_failure_rolls_back_mutation_and_blocks_reads; test_append_only_protect_and_catalog_validation; test_audit_minimizes_content_and_records_actor |
| CA-07 / RNF-02/03/04 | middleware, telas e PWA | test_privacy_headers_cover_csrf_methods_missing_and_redirects; tests/e2e/surgery_journeys.spec.js: mobile/axe e offline; gates acima |

Entrada inválida/UUID desconhecido e preservação da chave: test_invalid_form_preserves_key_and_active_get_choices. Fixture `tests/e2e/prepare_surgery_journeys.py` integrada ao runner de CI existente, com catálogo/encontro/operadores e concessão sintéticos. Auditoria ocorre após paginação, queries relacionadas sem N+1. Não há SurgicalSchedule/Material, agenda, execução cirúrgica, evento, checklist ou decisão clínica nesta entrega.
