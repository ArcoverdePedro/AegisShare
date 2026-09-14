# Contrato de Rotas — Spec 002 ADT

Todas as rotas ADT entregues são internas, renderizadas por Django e autenticadas por sessão. Nenhuma rota ADT é API REST pública.

## Superfície entregue

| Método | URL | View | Template/Resposta | Capacidade mínima |
|---|---|---|---|---|
| GET | `/admissoes/` | `AdmissionListView` | `clinical/adt/admission_list.html` | `adt.view_admission` |
| GET | `/admissoes/nova/` | `AdmissionCreateView` | `clinical/adt/admission_form.html` | `adt.admit_patient` |
| POST | `/admissoes/nova/` | `AdmissionCreateView` | redirect/form errors | `adt.admit_patient` + escopo PEP + escopo do local |
| GET | `/leitos/` | `BedMapView` | `clinical/adt/bed_map.html` | `adt.view_bed_map` |
| GET | `/leitos/mapa/` | `BedMapPartialView` | `clinical/adt/_bed_map.html` | `adt.view_bed_map` |
| GET | `/transferencias/nova/` | `TransferCreateView` | `clinical/adt/transfer_form.html` | `adt.transfer_patient` |
| POST | `/transferencias/nova/` | `TransferCreateView` | redirect/form errors | `adt.transfer_patient` + escopo PEP + escopo do local |
| GET | `/altas/nova/` | `DischargeCreateView` | `clinical/adt/discharge_form.html` | `adt.discharge_patient` |
| POST | `/altas/nova/` | `DischargeCreateView` | redirect/form errors | `adt.discharge_patient` + escopo PEP + escopo do local |

## Rotas inicialmente previstas e não expostas neste incremento

O contrato inicial reservava uma view dedicada de histórico e mutações operacionais de bloqueio/desbloqueio de leito. Elas **não fazem parte da superfície HTTP entregue nesta versão**:

- `/admissoes/<uuid:id>/historico/` — o histórico canônico já é preservado pelos modelos append-only `Admission`, `BedOccupancy`, `Transfer`, `Discharge` e pelo auditlog; uma tela dedicada pode ser entregue em incremento posterior sem alterar o histórico armazenado;
- `/leitos/<uuid:id>/bloquear/` e `/leitos/<uuid:id>/desbloquear/` — `Bed.operational_status` e a capacidade `adt.manage_bed_status` existem no domínio, mas nenhuma mutação HTTP de estado operacional foi exposta nesta fase.

Essa distinção evita documentar endpoints inexistentes e não cria compatibilidade fictícia.

## Regras HTTP

- mutações entregues são exclusivamente `POST` + CSRF;
- GET nunca muda estado;
- respostas ADT usam `Cache-Control: private, no-store, max-age=0` e `Vary: Cookie, HX-Request`;
- conflito de ocupação retorna formulário com erro seguro, sem SQL/stacktrace;
- objetos fora do escopo não são incluídos nos querysets autorizados;
- partial HTMX não é armazenado pelo service worker;
- admissão, transferência e alta são `network-only` e não usam `AegisOfflineQueue`;
- views não expõem nomes de permissão, IDs de usuário ou detalhes internos desnecessários em mensagens de erro.

## WebSocket

Canal entregue:

`/ws/clinical/adt/bed-map/`

O socket é autenticado por sessão e serve apenas como sinal de invalidação. Antes de cada envio, `AdtBedMapConsumer` revalida `adt.view_bed_map` e o escopo do local. O navegador recebe somente metadados técnicos mínimos e então refaz `GET /leitos/mapa/`, fazendo a autorização e a minimização de PHI novamente no servidor.

O contrato técnico correspondente está em `events.asyncapi.yaml`.

## Garantia de ausência de API REST pública

`aegis_share.tests.test_architecture.PublicApiArchitectureTests` congela a superfície `/api/` nos três endpoints legados já existentes antes do ADT. `AdtContractTests.test_adt_does_not_define_public_api_routes` adiciona uma garantia local de que `apps.clinical.adt.urls` não introduz prefixo `api/`.
