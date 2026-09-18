# Evidências locais — RIS v1 — 2026-09-18

Aprovação explícita do recorte: “[@Ponytail] aprovado, continue”, após a apresentação da Spec 006 de pedidos de imagem, com DICOM/viewer/laudos em extensões posteriores. Conclusão técnica para piloto sintético; validação institucional continua separada.

| Verificação | Resultado |
|---|---|
| Suíte completa Django / PostgreSQL 18 | 463 testes, todos passaram; inclui concorrência RIS e regressões dos módulos existentes |
| RIS / SQLite | 11 testes HTTP/domínio passaram antes dos testes concorrentes, que requerem PostgreSQL |
| Ruff check / format | Passaram nos arquivos Python do RIS, fixture e configuração alterada |
| Django check / makemigrations --check --dry-run | Sem problemas / sem alterações |
| Migration SQLite descartável | Aplicar ris.0001, reverter para zero e reaplicar: OK |
| Playwright Chromium, sem retries | 5 jornadas passaram na execução final; teste de revogação corrigido para o prefixo existente aegis-admin |
| Mobile/axe | Lista/form/detalhe em 390×844 e 768×1024 sem overflow e sem violações sérias/críticas WCAG |
| Offline | Sem confirmação; contagens/nomes IndexedDB inalterados; páginas /imagem/ e conteúdo sintético ausentes de Cache Storage; nome sintético ausente de localStorage/sessionStorage |
| Inspeção visual | Tela do pedido em telefone conferida; formulário e navegação renderizados |
| Logs sintéticos | Nome do paciente/exame e código privado ausentes dos logs de servidor e suíte PostgreSQL |
| Bandit / pip-audit | Sem findings no app RIS (testes excluídos) / sem vulnerabilidades conhecidas nas dependências instaladas |
| Lighthouse, raiz pública local | Acessibilidade 0,98; boas práticas 1,00; SEO 0,90; desempenho 0,42, aviso abaixo de 0,90. Gates de erro passaram; coleta ocorreu junto com outros testes locais |

Lighthouse público não mede a jornada autenticada, verificada via Playwright/axe. Nenhum novo JS ou dependência de aplicação foi adicionado. Não houve execução de CI remoto ou implantação. Fixtures, contas e bancos são sintéticos. Ausência de logs clínicos verificada com marcadores sintéticos nesta execução; auditlog minimizado está coberto pelos testes abaixo.

## Requisito → superfície → teste executável

Paths Python relativos a `apps/clinical/ris/tests/test_workflow.py`, salvo indicação explícita. Gherkin documenta critérios; Django e Playwright são os testes executáveis.

| Critério / requisito | Superfície | Evidência executável |
|---|---|---|
| CA-01 / RF-01/02 | Admin, order_create, order_form | test_snapshot_retry_and_new_operation; test_append_only_protect_and_catalog_validation; E2E pedido/retry |
| CA-02 / RF-03/04 | capacidades e escopo em todas as FBVs | test_capabilities_and_internal_role_are_required; test_revocation_and_inactive_patient_hide_history; E2E fora do escopo e revogação pelo Admin após abrir form |
| CA-03 / RF-04 | order_create / revalidação com lock | test_closed_encounter_blocks_new_and_retry_but_preserves_read |
| CA-04 / RF-05/08 | order_list/detail e templates | test_pagination_audits_only_visible_records_without_n_plus_one; test_audit_minimizes_content_and_records_actor |
| CA-05 / RF-06/07 | order_exam, constraint e snapshots | test_snapshot_retry_and_new_operation; test_conflicting_key_does_not_reveal_original; tests/test_concurrency.py: retry idêntico e colisão entre encontros no PostgreSQL |
| CA-06 / RF-07/08 | transação, auditlog, consultas | test_audit_failure_rolls_back_mutation_and_blocks_reads; test_append_only_protect_and_catalog_validation; test_audit_minimizes_content_and_records_actor |
| CA-07 / RNF-02/03/04/05 | middleware, telas e PWA | test_privacy_headers_cover_csrf_methods_missing_and_redirects; tests/e2e/ris_journeys.spec.js: mobile/axe e offline; gates acima |

Form inválido/UUID desconhecido e preservação da chave: test_invalid_form_preserves_key_and_active_get_choices. As consultas relacionadas da lista são limitadas e a auditoria ocorre somente após paginação. Não foi criado `ImagingStudy`, Report, evento, parser, viewer ou transporte de imagem.

Fixture `tests/e2e/prepare_ris_journeys.py` integrada ao CI já existente; cria catálogo, pacientes/encontros e operadores sintéticos, incluindo concessão revogável. Os nomes de testes E2E são seus próprios cenários no arquivo.
