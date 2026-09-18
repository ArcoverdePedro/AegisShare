# Spec 007 — Centro Cirúrgico v1: solicitações de procedimentos

## Status

**Autorizada em 2026-09-18** pela resposta “[@Ponytail] continue” à pergunta de aprovação deste recorte. Implementação realizada; [evidências locais](validation.md) e [guia operacional](../../docs/centro-cirurgico.md).

## Recorte e sequenciamento

O roadmap coloca Centro Cirúrgico após LIS e RIS/PACS na fase 3. Esta v1 registra uma solicitação de procedimento de catálogo institucional ligada ao encontro canônico do PEP. Não agenda, autoriza clinicamente nem confirma realização de cirurgia.

A aprovação deste recorte inclui o sequenciamento: registro de solicitações primeiro; mapa de salas/equipes, materiais, execução, checklist e recuperação em extensões com contratos próprios. Não chamar o registro de consentimento, avaliação de risco, aptidão ou autorização cirúrgica.

## User stories

- Como profissional interno autorizado, quero registrar uma solicitação de procedimento para um encontro aberto e acessível no PEP.
- Como profissional autorizado, quero consultar a solicitação original com procedimento, paciente/encontro, autor e horário preservados.
- Como operador, quero repetir um envio interrompido sem criar uma segunda solicitação ou alterar a original.

## Requisitos

- **RF-SURG-01:** catálogo `Procedure` com UUID, código técnico único, nome e ativo. Admin Django, staff interno e permissões nativas. Código/nome obrigatórios, removendo espaços externos; código exato, sensível a maiúsculas. Sem procedimentos pré-carregados ou dados de paciente nos campos de catálogo.
- **RF-SURG-02:** `SurgicalCase` representa somente uma solicitação nesta v1, para um `pep.Encounter` e um procedimento ativo. Guardar retrato de código/nome, ator e horário do servidor. Um procedimento por solicitação; nenhum campo livre de diagnóstico, justificativa, prioridade, risco, anestesia ou consentimento.
- **RF-SURG-03:** exigir sessão, `is_internal_professional`, `surgery.view_cases` e `accessible_patients(user)` em cada superfície identificável; criação exige também `surgery.request_procedure`. Capacidade não concede acesso PEP. ADM clínico não substitui capacidade; superusuário segue Django, com requisito de papel interno.
- **RF-SURG-04:** encontro OPEN para criar e repetir POST, revalidando escopo/capacidades/status sob lock. Fechado: 409, inclusive retry. Histórico consultável dentro do escopo PEP atual; paciente inativo ou concessão revogada oculta dados e bloqueia envio, inclusive formulário já aberto.
- **RF-SURG-05:** lista paginada de 25, detalhe e entrada pelo encontro. Mostrar protocolo, paciente/encontro autorizados, retrato do procedimento, ator e horário. Aviso “Solicitação registrada — sem agendamento ou autorização cirúrgica”. Não criar coluna de estado para um único estado nem sugerir cirurgia realizada.
- **RF-SURG-06:** `operation_key` UUID oculto com unicidade global no módulo. Mesmo ator/chave/encontro/procedimento retorna original após autorização atual e encontro aberto, preservando autor/horário/retrato e auditando ACCESS. Procedimento desativado admite apenas retry existente. Chave incompatível: 409 genérico sem revelar registro conflitante. Nova chave é nova solicitação, exigindo procedimento ativo; não deduplicar por paciente/nome.
- **RF-SURG-07:** solicitações append-only nas entradas da aplicação, sem edição/cancelamento/exclusão ou Admin. Retrato preservado após alteração do catálogo. FKs PROTECT para encontro/procedimento/ator; sem promessa de resistência a escrita direta no ORM/banco.
- **RF-SURG-08:** criação e auditoria atômicas; falha reverte mutação e não confirma. Auditar CREATE/ACCESS com ator; lista apenas após paginação, para itens renderizados. Falha na auditoria de leitura não entrega conteúdo identificável. Logs/auditlog genérico excluem código/nome/retrato do procedimento e nome do paciente.

## Requisitos não funcionais

- **RNF-SURG-01:** app `apps.clinical.surgery`, Forms, FBVs e DTL. Reusar usuário/PEP, Admin, auditlog, layout e middleware privado. Sem dependência nova, JS próprio, CBV, base genérica de solicitações, worker ou fila.
- **RNF-SURG-02:** `/cirurgias/` com private/no-store, Vary Cookie e nosniff, inclusive redirects/CSRF/erros. Exceções protegidas contra parâmetros/variáveis clínicos; nenhum erro revela solicitação conflitante. Sem API REST pública.
- **RNF-SURG-03:** exclusivamente online, sem Cache Storage/IndexedDB/fila offline para solicitações, sem push/WebSocket/evento sem consumidor. Telefone/tablet sem overflow, labels acessíveis e axe sem violações sérias/críticas.
- **RNF-SURG-04:** relações da lista via select_related; paginação antes da auditoria e sem queries por item. Migration reversível, concorrência PostgreSQL, rollback de auditoria e evidências reais; aprovação institucional de uso real separada da entrega técnica.

## Fora de escopo e gates posteriores

`SurgicalSchedule`, salas, intervalos, equipe/escala, urgência, agendamento/reagendamento/cancelamento, reserva/baixa de materiais, estoque, confirmação de execução, checklist, consentimento, avaliação de risco, anestesia, recuperação, alta pós-operatória, cobrança, assinatura ou decisão clínica.

Mapa cirúrgico exige salas/recurso canônico, escopo operacional (avaliando Location/UserLocationAccess ADT), duração/intervalos, equipes e política de conflitos/reagendamento. Materiais exigem contrato com Spec 009 e rastreabilidade de lote, sem criar estoque paralelo ao da farmácia. Checklist/recuperação exigem governança clínica, autoria, estados, exceções e assinatura aplicável. Não inventar estes significados.

`surgery.scheduled`, `surgery.started` e `surgery.finished` do roadmap completo não existem neste recorte: nenhuma dessas ações acontece. Publicação futura exige consumidor e contrato mínimo após commit, com helper de eventos existente.

## Rastreabilidade

| Requisito | Superfície implementada | Aceitação |
|---|---|---|
| 01/02 | Admin Procedure; case_create / case_form | CA-SURG-01 |
| 03/04 | todas as FBVs; lock de encontro | CA-SURG-02/03 |
| 05/08 | case_list/detail / lista e detalhe | CA-SURG-04/06 |
| 06/07 | POST, snapshots, constraint e retries | CA-SURG-05 |
| 07/08 | transação/auditlog/erros | CA-SURG-06 |
| RNF-02/03/04 | middleware, telas, PWA e gates | CA-SURG-07 |

[Modelo](data-model.md), [contratos](contracts/routes-and-forms.md), [inventário](research.md), [plano](plan.md), [tarefas](tasks.md), [aceitação](features/cases.feature). Testes executáveis e resultados em [validation.md](validation.md).

## Definition of Done

- [x] Recorte, inventário, modelo, contratos, plano, tarefas e aceitação preparados.
- [x] Aprovação explícita deste recorte e sequenciamento.
- [x] Implementação, migration reversível e testes HTTP/domínio.
- [x] Concorrência PostgreSQL, auditoria/rollback, revogação e privacidade.
- [x] E2E, telefone/tablet/axe/offline e gates locais com evidências reais.
- [x] Guia operacional e rastreabilidade para testes executáveis.
- [ ] Validação institucional antes de uso real.
