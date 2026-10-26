# Agenda ambulatorial, chegada e fila (H11)

App `apps/clinical/scheduling`, FBVs em `/agenda/`. Escopo provisório (G01 pendente): ambulatório de hospital geral. Não registra dado clínico; a chegada abre o `Encounter` canônico do PEP.

## Capacidades

| Permissão (`scheduling.*`) | Uso |
| --- | --- |
| `view_agenda` | agenda do dia, fila e detalhe (detalhe exige também acesso ao paciente no PEP) |
| `manage_agenda` | abrir horários em lote (até 96 por vez, idempotente por profissional+início) e bloquear com motivo |
| `book_appointment` | agendar a partir do prontuário ("Agendar consulta"), remarcar e cancelar com motivo |
| `overbook_appointment` | encaixe acima da capacidade, com justificativa |
| `checkin_appointment` | chegada, chamada e falta (falta só após o início do horário) |

## Regras

- Capacidade verificada com o horário travado (`select_for_update`); disputa pela última vaga gera um agendamento e um conflito (teste PostgreSQL). Mesmo paciente não fica ativo duas vezes no mesmo horário (constraint parcial). `operation_key` torna o envio repetido idempotente.
- Estados: Agendado → Chegou → Chamado; Agendado → Cancelado/Remarcado/Falta. Remarcar cria novo agendamento ligado ao anterior (`rescheduled_from`), que fica "Remarcado" — histórico preservado.
- Chegada cria um único `Encounter` (consulta, local do horário, profissional do horário como responsável) e emite `encounter.created` após o commit.
- Bloquear horário não cancela agendamentos existentes: a tela orienta remarcar.
- Privacidade: nomes só aparecem a quem já acessa o paciente pelas regras do PEP; demais veem a senha curta. Rotas `/agenda/` são `private, no-store`. Não há painel público nem confirmação externa (sem canal autorizado).

## Pendentes

G01 (unidades/serviços reais), H02/G02 (perfil de recepção e acesso do profissional ao paciente agendado — hoje não há concessão automática), H26 (escala/afastamento do profissional bloqueando agenda), lembretes por canal externo autorizado e painel de chamada público com senha.
