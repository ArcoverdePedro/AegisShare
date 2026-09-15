# Rastreabilidade — Spec 004 Enfermagem

> Estado: matriz inicial de design. As colunas de código/teste concreto serão atualizadas durante implementação após aprovação da spec.

| Requisito | Contrato/decisão | Código previsto | Teste/aceitação |
|---|---|---|---|
| RF-NUR-01 | `spec.md`, `access-policy.md` | `nursing` -> `PEP.Encounter` | boundary de escopo PEP |
| RF-NUR-02 | `data-model.md` | `VitalSignsRecord` + form | model/form/view |
| RF-NUR-03 | `data-model.md` | campos com unidades canônicas | validação estrutural; nenhuma interpretação clínica |
| RF-NUR-04 | `data-model.md` | `recorded_at` + `created_at` | coerência temporal |
| RF-NUR-05 | `data-model.md` | `replaces` append-only | correção preserva original |
| RF-NUR-06 | `offline-vital-signs.md` | integração com `AegisOfflineQueue` existente | Playwright offline + ciphertext |
| RF-NUR-07 | `offline-vital-signs.md` | rotina server-side idempotente | duplicate retry + encounter closed + access lost |
| RF-NUR-08 | `data-model.md`, gate T-NUR-09 | selector de peso/proveniência | contrato de selector + RX continua NOT_EVALUABLE enquanto gate aberto |
| RF-NUR-09 | `medication-administration.md` | FK `MedicationDispenseItem` | rastreabilidade até lote/prescrição |
| RF-NUR-10 | `medication-administration.md` | campos dose/unidade explícitos | sem conversão/inferência automática |
| RF-NUR-11 | `medication-administration.md` | `operation_key` unique | retry/double-click idempotente |
| RF-NUR-12 | `offline-vital-signs.md`, `medication-administration.md` | nenhuma fila para administração | Playwright network-only |
| RF-NUR-13 | `access-policy.md` | permissions + queries PEP-scoped | RBAC/ABAC + 404 seguro |
| RF-NUR-14 | `events.asyncapi.yaml` | audit + `transaction.on_commit()` | audit/events sem PHI |
| RNF-NUR-01 | `data-model.md` | PostgreSQL | integration tests |
| RNF-NUR-02 | `data-model.md` | services/forms sem update destrutivo | imutabilidade |
| RNF-NUR-03 | `routes.md` | FBVs server-rendered; sem `/api/` pública | teste arquitetural |
| RNF-NUR-04 | todos os contratos | logging/eventos minimizados | assert de payload/log sem PHI |
| RNF-NUR-05 | `spec.md` | templates responsivos | axe-core + 390px/tablet |
| RNF-NUR-06 | offline/admin contracts | UUID idempotência + erros seguros | conflict/retry tests |
| RNF-NUR-07 | `plan.md` | migrations próprias do app | `makemigrations --check` + reversibilidade |
| RNF-NUR-08 | `offline-vital-signs.md` | fila PWA existente | ausência de segunda infraestrutura offline |

## Gates externos rastreados

| Gate | Impacto | Estado |
|---|---|---|
| T-NUR-09 — política de atualidade/origem do peso | impede consumo automático do peso pelo RX | BLOCKED governança clínica/farmacêutica |
| T-NUR-11 — exceções de administração | impede modelar recusa/omissão/atraso/dose divergente | BLOCKED governança clínica/operacional |
| faixas de normalidade/alertas | impede interpretação automática de sinais vitais | fora de escopo até referência aprovada |

## Dependências cruzadas

- Spec 001 fornece paciente, encontro e escopo clínico.
- Spec 002 pode fornecer contexto de local/leito, sem ampliar acesso PEP.
- Spec 003 fornece prescrição, dispensação e lote; continua `NOT_EVALUABLE` para peso até fechamento do gate correspondente.
- Spec 014 fornece fila local cifrada, limpeza no logout e contrato geral de sincronização.

## Critério de fechamento da spec

Spec 004 só pode ser marcada como implementada quando:

1. todos os itens não bloqueados de `tasks.md` estiverem concluídos;
2. CI determinístico estiver verde;
3. Gherkin/Playwright cobrirem jornadas online/offline e negações;
4. axe-core/mobile passarem;
5. administração continuar comprovadamente network-only;
6. blockers externos permanecerem explicitamente abertos se ainda não aprovados.
