# Contrato de Rotas — Spec 002 ADT

Todas as rotas são internas, renderizadas por Django e autenticadas por sessão. Nenhuma rota abaixo é API REST pública.

| Método | URL | View prevista | Template/Resposta | Capacidade mínima |
|---|---|---|---|---|
| GET | `/admissoes/` | `AdmissionListView` | `clinical/adt/admission_list.html` | `adt.view_admission` |
| GET | `/admissoes/nova/` | `AdmissionCreateView` | `clinical/adt/admission_form.html` | `adt.admit` |
| POST | `/admissoes/nova/` | `AdmissionCreateView` | redirect/form errors | `adt.admit` + escopo PEP |
| GET | `/admissoes/<uuid:id>/historico/` | `MovementHistoryView` | `clinical/adt/movement_history.html` | `adt.view_admission` + escopo PEP quando houver PHI |
| GET | `/leitos/` | `BedMapView` | `clinical/adt/bed_map.html` | `adt.view_bed_map` |
| GET | `/leitos/mapa/` | `BedMapPartialView` | `clinical/adt/_bed_map.html` | `adt.view_bed_map` |
| POST | `/leitos/<uuid:id>/bloquear/` | `BedBlockView` | redirect/partial | `adt.manage_bed_status` |
| POST | `/leitos/<uuid:id>/desbloquear/` | `BedUnblockView` | redirect/partial | `adt.manage_bed_status` |
| GET | `/transferencias/nova/` | `TransferCreateView` | `clinical/adt/transfer_form.html` | `adt.transfer` |
| POST | `/transferencias/nova/` | `TransferCreateView` | redirect/form errors | `adt.transfer` + escopo PEP |
| GET | `/altas/nova/` | `DischargeCreateView` | `clinical/adt/discharge_form.html` | `adt.discharge` |
| POST | `/altas/nova/` | `DischargeCreateView` | redirect/form errors | `adt.discharge` + escopo PEP |

## Regras HTTP

- mutações são exclusivamente `POST` + CSRF;
- GET nunca muda estado;
- conflito de ocupação retorna formulário com erro seguro e status compatível, sem SQL/stacktrace;
- objetos fora do escopo retornam 404 quando a existência em si for informação sensível;
- partial HTMX usa `Vary`/cache apropriado e não deve ser armazenado pelo service worker;
- views não expõem nomes de permissão, IDs de usuário ou detalhes internos desnecessários em mensagens de erro.

## WebSocket

Canal previsto:

`/ws/clinical/adt/bed-map/`

O socket é autenticado por sessão e serve apenas para sinalizar que o mapa deve ser atualizado. O cliente então refaz `GET /leitos/mapa/`, permitindo que a autorização e a minimização de PHI sejam reavaliadas no servidor.
