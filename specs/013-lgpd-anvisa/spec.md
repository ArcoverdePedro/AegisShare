# Spec 013 — Solicitações do titular e governança de dados

## Status

**Aprovada pelo mantenedor em 2026-09-16**, pela instrução “aprovado, continue”. Implementação do recorte v1 e contratos autorizada; uso com dados reais permanece sujeito ao procedimento institucional.

## Contexto

O Core documenta o inventário técnico em [privacy-retention.md](../000-core/contracts/privacy-retention.md). Os módulos clínicos preservam histórico e escopo PEP. A Spec 012 já permite exportação mínima por arquivo, mas não constitui atendimento completo a uma solicitação do titular.

O recorte P0 implementado permite registrar e acompanhar solicitações referentes a **pacientes já cadastrados e acessíveis no PEP**. O sistema registra o trabalho administrativo; não decide bases legais, valida identidade automaticamente, concede acesso clínico nem executa exclusão, correção, anonimização ou exportação em consequência de uma solicitação.

## User Stories

- Como profissional interno autorizado, quero registrar uma solicitação recebida pelo canal institucional para que seu acompanhamento seja rastreável.
- Como responsável autorizado pelo atendimento, quero iniciar análise e registrar o encerramento, preservando autor, horário e histórico.
- Como profissional que consulta o histórico, quero distinguir o encerramento administrativo da execução de uma ação sobre os dados.

## Requisitos Funcionais

- **RF-LGP-01:** registrar solicitação com paciente, categoria e resumo obrigatório; gerar protocolo UUID, autor, horário do servidor e estado `RECEIVED`.
- **RF-LGP-02:** listar solicitações paginadas e apresentar detalhe com histórico cronológico; categorias: acesso, correção, exclusão, portabilidade e outra. São classificações de entrada, não decisões sobre direitos ou obrigações.
- **RF-LGP-03:** exigir sessão, profissional interno, capacidades específicas e escopo atual `accessible_patients(user)` em cada GET/POST. Atribuir capacidade não cria `PatientAccessGrant`.
- **RF-LGP-04:** permitir somente `RECEIVED → IN_REVIEW → CLOSED`. Iniciar análise admite nota opcional; encerrar exige nota de atendimento. Estado encerrado não significa pedido deferido ou ação executada.
- **RF-LGP-05:** preservar eventos append-only com estado anterior/novo, ator e horário. Cadastro inicial e evento inicial são atômicos; transição e evento são atômicos. Sem edição/exclusão de resumo ou histórico nesta versão.
- **RF-LGP-06:** rejeitar transição concorrente ou baseada em formulário desatualizado com 409, sem duplicar eventos ou sobrescrever nota. Revalidar acesso antes da mutação.
- **RF-LGP-07:** auditar leitura de solicitações efetivamente renderizadas e suas mutações, sem resumo, nota, nome, CPF ou conteúdo clínico no auditlog genérico ou logs de aplicação.
- **RF-LGP-08:** manter respostas sensíveis `private, no-store`, com fluxo exclusivamente online, sem IndexedDB, push ou API REST pública.

## Requisitos Não Funcionais

- **RNF-LGP-01:** reusar autenticação, permissões Django, queryset PEP, auditlog, layouts e testes do monólito; novas views são FBVs.
- **RNF-LGP-02:** forms Django validam campos/categorias/estado; templates escapam texto livre. Nenhum dado pessoal em query string; filtro GET admite somente estado administrativo e página.
- **RNF-LGP-03:** consultas paginadas, `select_related` para paciente/ator; sem N+1. Concorrência validada no PostgreSQL com bloqueio de linha.
- **RNF-LGP-04:** telefone/tablet sem overflow, labels/erros acessíveis e axe sem violações sérias/críticas.
- **RNF-LGP-05:** falha ao gravar evento ou auditoria reverte a operação; resposta operacional genérica, sem traceback/PHI.

## Critérios de Aceitação

[features/data-subject-requests.feature](features/data-subject-requests.feature) define CA-LGP-01 a CA-LGP-07. A matriz abaixo vincula os cenários aos testes Django e Playwright implementados. Não há runner BDD adicional.

## Telas e Fluxos

Lista → nova solicitação → detalhe → iniciar análise → registrar encerramento → detalhe com histórico. O formulário orienta registrar apenas o resumo necessário, sem anexar documentos de identidade ou transcrever prontuário.

Nenhuma ação desse fluxo chama exportação da Spec 012, altera paciente, cria concessão de acesso ou aciona expurgo. A interface rotula o estado final como **Encerrada administrativamente**.

## Fora de Escopo

Portal público, solicitações de pessoas sem cadastro PEP, identidade/representação verificada automaticamente, consentimentos, bases legais automáticas, prazos/SLA legais, respostas por e-mail, assinatura, anexos, links públicos, reabertura, integração automática com exportação, exclusão/anonimização, retenção/expurgo, RiskAssessment e certificação ANVISA.

## Dependências

Specs 000, 001 e 014. A Spec 012 é referência de minimização/auditoria e permanece independente. Usar somente dados sintéticos no piloto até existir procedimento institucional de recebimento, conferência de identidade/representação, acesso e atendimento.

## Riscos

- Resumo e nota podem conter dados sensíveis: limitar tamanho, orientar minimização, controlar leitura e excluí-los do auditlog/logs.
- Encerramento pode ser confundido com execução: usar texto explícito e não produzir efeito sobre os dados do paciente.
- Escopo PEP atual exclui pacientes inativos: v1 não amplia esse escopo; atendimento nesses casos exige processo institucional fora desta UI.
- Ausência de política de retenção: preservar registros nesta versão; nenhum prazo ou expurgo é inferido.
- Modelos append-only na aplicação não impedem alteração por administrador do banco; não afirmar imutabilidade criptográfica.

## Rastreabilidade

Testes de servidor: `apps/compliance/tests/test_requests.py` e `test_concurrency.py`. E2E: `tests/e2e/compliance_journeys.spec.js`, com preparação em `prepare_compliance_journeys.py`.

| Requisitos | Rota/View | Template | Critério | Teste implementado |
|---|---|---|---|---|
| RF-LGP-01/05 | `request_create` | `compliance/request_form.html` | CA-LGP-01 | `test_creation_ignores_client_status_and_actor_and_is_audited`; Playwright CA-LGP-01/02/07 |
| RF-LGP-02/07; RNF-LGP-03/04 | `request_list`, `request_detail` | lista/detalhe | CA-LGP-02/07 | `test_filter_pagination_and_only_visible_access_audit`; `test_patient_and_actor_selects_do_not_grow_with_list_size`; Playwright mobile/axe |
| RF-LGP-03 | todas as FBVs | lista/form/detalhe | CA-LGP-03 | `test_revoked_or_expired_grant_between_get_and_post`; `test_capabilities_are_independent_and_require_view`; Playwright CA-LGP-03 |
| RF-LGP-04/05 | `request_transition` | `compliance/request_transition.html` | CA-LGP-02/04 | `test_complete_flow_preserves_history_without_patient_mutation_or_export`; `test_invalid_transition_and_replay_are_conflicts`; Playwright CA-LGP-01/02/04 |
| RF-LGP-06; RNF-LGP-03 | `request_transition` | erro 409 | CA-LGP-04 | `RequestConcurrencyTests` no PostgreSQL |
| RF-LGP-07; RNF-LGP-02/05 | todas as FBVs | HTML escapado/erro seguro | CA-LGP-05/07 | `test_transition_audit_failure_rolls_back_state_and_event`; `test_creation_event_failure_rolls_back_request_and_audit`; `test_notes_are_escaped_and_excluded_from_audit` |
| RF-LGP-08 | todas as FBVs + fronteira PWA | no-store/fallback | CA-LGP-06 | Playwright privacidade/offline; testes de cabeçalhos |

## Definition of Done

- [x] Proposta, plano, modelo, contratos, tarefas e aceitação preparados.
- [x] Aprovação explícita da spec e contratos.
- [x] Implementação, migration reversível e autorização por objeto.
- [x] Auditoria, validação transacional/concorrência e testes de falha.
- [x] Testes HTTP, E2E, mobile/axe e privacidade PWA.
- [x] Gates locais executados (CI remoto não executado) e limitações registradas sem equivaler testes técnicos a certificação.
- [x] Guia operacional e rastreabilidade com testes reais.
