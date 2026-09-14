# Rastreabilidade final — Spec 002 ADT

> Referência: Spec 002 aprovada em 2026-09-14. Este documento registra a implementação efetivamente entregue e os testes que fecham cada requisito, sem alterar retroativamente a spec aprovada.

## Matriz requisito → implementação → evidência

| Requisito | Implementação principal | Evidência automatizada |
|---|---|---|
| RF-ADT-01 Admissão | `Admission`, `AdmissionForm`, `AdmissionCreateView`, `admit_patient()` | `test_models.py`, `test_services.py`, `test_views.py`, `adt_journeys.spec.js` |
| RF-ADT-02 Ocupação exclusiva | constraints parciais de `BedOccupancy`, locking transacional | `test_models.py`, `test_admission_concurrency.py` |
| RF-ADT-03 Mapa de leitos | `BedMapView`, `BedMapPartialView`, `bed_map_groups()` | `test_views.py`, `adt_journeys.spec.js` |
| RF-ADT-04 Transferência | `Transfer`, `TransferForm`, `TransferCreateView`, `transfer_patient()` | `test_lifecycle.py`, `test_lifecycle_views.py`, `test_transfer_concurrency.py`, `adt_journeys.spec.js` |
| RF-ADT-05 Alta | `Discharge`, `DischargeForm`, `DischargeCreateView`, `discharge_patient()` | `test_lifecycle.py`, `test_lifecycle_views.py`, `adt_journeys.spec.js` |
| RF-ADT-06 Histórico | `Admission`, `BedOccupancy`, `Transfer` e `Discharge` preservam sequência; transferência/alta são append-only; auditlog mantém trilha | `test_models.py`, `test_lifecycle.py`, `test_audit_events.py` |
| RF-ADT-07 Autorização | `permissions.py`, selectors autorizados, filtros PEP/local e deny-by-default | `test_permissions.py`, `test_views.py`, `test_lifecycle_views.py`, `adt_journeys.spec.js` |
| RF-ADT-08 Auditoria | `django-auditlog` + `accessed` para leituras sensíveis; campos textuais sensíveis excluídos | `test_audit_events.py` |
| RF-ADT-09 Tempo real | `emit_adt_event()` pós-commit, `AdtBedMapConsumer`, refresh HTMX autorizado | `test_audit_events.py`, contrato `events.asyncapi.yaml` |
| RF-ADT-10 Integração interna | allowlist `ADT_EVENT_TYPES` e contrato AsyncAPI alinhado ao runtime | `test_contracts.py`, `test_audit_events.py` |
| RF-ADT-11 Concorrência | `transaction.atomic()`, `select_for_update()`, constraints PostgreSQL e rollback seguro | `test_admission_concurrency.py`, `test_transfer_concurrency.py` |
| RF-ADT-12 PWA | mutações ADT sem runtime de fila, POST ignorado pelo service worker e páginas `no-store` | `adt_journeys.spec.js` — cenário `network-only` |
| RNF-ADT-03 Sem API REST pública | somente Django views/forms/HTMX/WebSocket; `/api/` permanece congelada na superfície legada | `PublicApiArchitectureTests`, `AdtContractTests.test_adt_does_not_define_public_api_routes` |
| RNF-ADT-06 Acessibilidade | templates server-rendered responsivos | `adt_journeys.spec.js` com axe-core WCAG 2.1 A/AA e viewports 390x844 / 768x1024 |

## Superfície HTTP final

As rotas efetivamente entregues estão em `contracts/routes.md`. São rotas de sessão Django sob:

- `/admissoes/` e `/admissoes/nova/`;
- `/leitos/` e `/leitos/mapa/`;
- `/transferencias/nova/`;
- `/altas/nova/`.

O WebSocket interno do mapa é `/ws/clinical/adt/bed-map/`.

Nenhuma rota ADT usa prefixo `/api/`.

## PWA e operação offline

Admissão, transferência e alta permanecem deliberadamente `network-only`. O teste de navegador:

1. garante um service worker ativo/controlando a página;
2. visita os três formulários críticos e confirma que seus caminhos não entram no Cache Storage;
3. confirma que o runtime `AegisOfflineQueue` não é carregado pelas páginas ADT;
4. corta a rede e tenta `POST` nos três endpoints;
5. exige falha de rede para todas as tentativas;
6. confirma novamente que o IndexedDB `aegisshare-offline` não foi criado e que nenhum endpoint mutável foi armazenado em cache.

Qualquer futura mutação ADT offline exige nova alteração de contrato na Spec 014 e revisão explícita deste requisito.

## Eventos e minimização

`apps/clinical/adt/events.py` mantém exatamente seis tipos permitidos:

- `encounter.admitted`;
- `encounter.transferred`;
- `encounter.discharged`;
- `bed.occupied`;
- `bed.released`;
- `bed.status_changed`.

`contracts/events.asyncapi.yaml` descreve tanto os eventos internos pós-commit quanto o sinal WebSocket entregue ao navegador. `AdtBedMapConsumer` remove IDs de encontro, admissão e ocupação do payload de navegador e revalida a autorização por local antes de enviar a invalidação.

`AdtContractTests` impede divergência silenciosa entre o allowlist do runtime e os nomes documentados no AsyncAPI.

## Decisões de superfície inicialmente reservadas

O contrato inicial citava uma tela dedicada de histórico e endpoints de bloqueio/desbloqueio. Eles não foram expostos como HTTP nesta entrega e, por isso, foram removidos da tabela de superfície entregue em `contracts/routes.md`:

- o histórico requerido por RF-ADT-06 já é preservado no modelo append-only e no auditlog; uma apresentação dedicada pode ser adicionada futuramente sem migrar ou reescrever o histórico;
- `Bed.operational_status` e `adt.manage_bed_status` permanecem disponíveis no domínio, mas a mutação operacional de status não recebeu rota pública/interna de formulário nesta fase.

Essa documentação evita declarar endpoints que não existem e preserva a possibilidade de evolução por uma spec incremental posterior.

## Gate de conclusão

A Spec 002 pode ser considerada tecnicamente concluída quando o CI do PR de fechamento comprovar, no mesmo commit:

- Django checks, migrations e suíte Python verdes em PostgreSQL/Redis;
- concorrência PostgreSQL verde;
- Playwright Core/PEP/ADT/PWA verde;
- axe-core e Lighthouse verdes;
- testes `network-only` ADT verdes;
- testes de contrato AsyncAPI e ausência de nova API REST pública verdes.
