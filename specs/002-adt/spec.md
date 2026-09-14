# Spec 002 — ADT: Admissão, Alta e Transferência

> Prioridade: P0  
> Dependência: Spec 001 — PEP  
> Status: aprovada pelo mantenedor em 2026-09-14

## Contexto

O módulo ADT controla o ciclo operacional da internação: admissão de um paciente já identificado no PEP, ocupação e liberação de leitos, transferências entre locais e alta. O SDD define como superfície principal `/admissoes/`, `/leitos/`, `/transferencias/` e `/altas/`, com mapa de leitos atualizado por HTMX + WebSocket e histórico de movimentação.

O `Encounter` já existe e pertence ao PEP. Esta spec não cria um segundo encontro concorrente: o ADT referencia o `apps.clinical.pep.models.Encounter` canônico e adiciona entidades próprias de ocupação/movimentação. Essa decisão evita duas fontes de verdade para o mesmo atendimento e é formalizada no ADR-0008.

## User Stories

- Como profissional de admissão autorizado, quero admitir um paciente em um encontro de internação para iniciar sua permanência hospitalar com leito rastreável.
- Como equipe assistencial autorizada, quero consultar o mapa de leitos em tempo quase real para saber quais leitos estão livres, ocupados, bloqueados ou indisponíveis.
- Como profissional autorizado, quero transferir uma internação entre leitos sem perder o histórico de movimentação.
- Como profissional autorizado, quero registrar a alta e liberar o leito de forma atômica para impedir ocupação residual.
- Como auditor, quero reconstruir toda a sequência de admissão, transferências e alta sem depender de edição destrutiva de registros anteriores.

## Requisitos Funcionais

- **RF-ADT-01 — Admissão.** Criar uma `Admission` para um `Encounter` do tipo internação e status aberto, associando paciente, local/leito inicial, data/hora e profissional responsável.
- **RF-ADT-02 — Ocupação exclusiva.** Um leito não pode possuir mais de uma ocupação ativa. Admissão e transferência devem validar novamente a disponibilidade dentro da transação de banco.
- **RF-ADT-03 — Mapa de leitos.** Exibir leitos por unidade/local com estado `AVAILABLE`, `OCCUPIED`, `BLOCKED` ou `OUT_OF_SERVICE`, sem expor PHI a usuários sem autorização clínica para o paciente ocupante.
- **RF-ADT-04 — Transferência.** Registrar transferência append-only entre origem e destino, encerrar a ocupação anterior e iniciar a nova ocupação de forma atômica.
- **RF-ADT-05 — Alta.** Registrar `Discharge`, encerrar a ocupação ativa e fechar o `Encounter` associado na mesma operação transacional.
- **RF-ADT-06 — Histórico.** Preservar histórico cronológico de admissão, ocupações, transferências, bloqueios administrativos e alta; registros clínico-operacionais concluídos não podem ser apagados pela interface comum.
- **RF-ADT-07 — Autorização.** Aplicar RBAC + ABAC: somente papéis/capacidades ADT autorizados podem admitir, transferir, bloquear/desbloquear ou dar alta; acesso a dados identificáveis do ocupante exige também escopo PEP válido.
- **RF-ADT-08 — Auditoria.** Registrar leituras sensíveis e todas as mutações ADT sem copiar nome, CPF, diagnóstico ou texto clínico para payloads de auditoria/eventos.
- **RF-ADT-09 — Tempo real.** Publicar mudanças do mapa após commit usando Channels; payload deve conter apenas identificadores técnicos/estado necessários para invalidar ou atualizar o fragmento autorizado.
- **RF-ADT-10 — Integração interna.** Emitir eventos `encounter.admitted`, `encounter.transferred`, `encounter.discharged` e `bed.occupied` para consumidores internos futuros, sem API REST pública.
- **RF-ADT-11 — Concorrência.** Conflitos de ocupação simultânea devem falhar de forma determinística, sem sobrescrever a movimentação vencedora.
- **RF-ADT-12 — PWA.** Consultas podem usar o shell PWA, mas admissões, transferências e altas permanecem `network-only` nesta versão. Nenhuma mutação ADT será enfileirada offline até contrato específico aprovado.

## Requisitos Não Funcionais

- **RNF-ADT-01** PostgreSQL é a fonte de verdade transacional para ocupação de leitos.
- **RNF-ADT-02** Admissão, transferência e alta devem usar `transaction.atomic()` e bloqueio/constraint compatível com prevenção de dupla ocupação.
- **RNF-ADT-03** Nenhuma rota REST pública será criada; toda interação é por Django views/forms/HTMX/WebSocket autenticados por sessão.
- **RNF-ADT-04** Eventos WebSocket e logs técnicos não devem conter PHI textual.
- **RNF-ADT-05** Operações críticas devem ser idempotentes na camada de serviço quando receberem a mesma chave de operação gerada pelo formulário.
- **RNF-ADT-06** Interfaces essenciais devem cumprir WCAG 2.1 AA e funcionar em desktop, tablet e smartphone.
- **RNF-ADT-07** O mapa deve refletir uma alteração confirmada em até 5 segundos em condições normais de rede interna.
- **RNF-ADT-08** Migrações devem ser reversíveis e não alterar tabelas existentes do PEP de forma destrutiva.

## Critérios de Aceitação

```gherkin
Cenário: admitir paciente em leito disponível
  Dado um paciente com encontro de internação aberto
  E um leito disponível
  E um profissional autorizado
  Quando ele confirma a admissão
  Então uma admissão é criada
  E o leito passa a ocupado
  E o histórico registra a movimentação
  E a auditoria registra a operação
  E o mapa é invalidado via evento interno sem PHI textual
```

```gherkin
Cenário: impedir dupla ocupação concorrente
  Dado um leito disponível
  E duas admissões concorrentes tentando ocupar o mesmo leito
  Quando as transações forem confirmadas
  Então somente uma ocupação permanece ativa
  E a outra operação recebe erro de conflito seguro
  E nenhum histórico vencedor é sobrescrito
```

```gherkin
Cenário: transferir paciente entre leitos
  Dado uma internação com ocupação ativa no leito A
  E o leito B disponível
  Quando um profissional autorizado confirma a transferência
  Então a ocupação do leito A é encerrada
  E uma nova ocupação no leito B é criada
  E uma transferência append-only liga origem e destino
  E ambas as alterações ocorrem na mesma transação
```

```gherkin
Cenário: alta libera leito e fecha encontro
  Dado uma internação com ocupação ativa
  Quando um profissional autorizado registra a alta
  Então a alta é persistida
  E a ocupação ativa é encerrada
  E o leito volta ao estado disponível quando não houver bloqueio
  E o encontro do PEP é fechado com horário de encerramento
```

```gherkin
Cenário: usuário sem escopo clínico consulta mapa
  Dado um leito ocupado
  E um usuário autenticado sem acesso PEP ao paciente
  Quando consulta o mapa de leitos
  Então ele pode ver somente o estado operacional permitido
  E não recebe nome, CPF, diagnóstico ou outro dado identificável do paciente
```

## Telas e Fluxos

- `clinical/adt/admission_list.html` — admissões ativas/recentes conforme escopo.
- `clinical/adt/admission_form.html` — confirmação de admissão.
- `clinical/adt/bed_map.html` + `_bed_map.html` — mapa e fragmento HTMX.
- `clinical/adt/transfer_form.html` — transferência de leito.
- `clinical/adt/discharge_form.html` — alta.
- `clinical/adt/movement_history.html` — histórico operacional append-only.

## Fora de Escopo

- faturamento e cobrança;
- prescrição/farmácia;
- regulação externa de vagas;
- reserva avançada de leito;
- housekeeping/manutenção com workflow completo;
- integração HL7/FHIR externa;
- mutações ADT offline;
- API REST pública.

## Dependências

- Spec 000 — Core: autenticação, auditoria e eventos internos.
- Spec 001 — PEP: `Patient`, `Encounter`, grants e autorização clínica.
- Spec 014 — PWA: shell/instalação; mutações ADT continuam network-only.
- Spec 013 — LGPD/ANVISA: retenção jurídica definitiva e políticas regulatórias futuras.

## Riscos

- dupla ocupação por corrida entre usuários;
- fechamento inconsistente entre alta e `Encounter`;
- exposição de PHI no mapa de leitos;
- eventos em tempo real entregues após revogação de acesso;
- relógio/ordenação incorreta de movimentos;
- tentativa de operar ADT offline com informação de leito obsoleta.

## Rastreabilidade inicial

| Requisito | Rota/View prevista | Template | Teste previsto |
|---|---|---|---|
| RF-ADT-01/02 | `/admissoes/nova/` / `AdmissionCreateView` | `admission_form.html` | unit + view + concorrência |
| RF-ADT-03/09 | `/leitos/` e `/leitos/mapa/` | `bed_map.html`, `_bed_map.html` | view + HTMX + WebSocket + a11y |
| RF-ADT-04/11 | `/transferencias/nova/` / `TransferCreateView` | `transfer_form.html` | unit + view + concorrência |
| RF-ADT-05 | `/altas/nova/` / `DischargeCreateView` | `discharge_form.html` | unit + view |
| RF-ADT-06/08 | `/admissoes/<id>/historico/` | `movement_history.html` | audit + authorization |
| RF-ADT-07 | todas as rotas ADT | todas | security boundary tests |
| RF-ADT-10 | serviços ADT | — | event contract tests |
| RF-ADT-12 | rotas mutáveis ADT | — | PWA security/E2E |
