# Contrato — Rotas da Enfermagem

Nenhuma rota REST pública é criada. Todas as superfícies são Django server-rendered ou rotas internas autenticadas por sessão e protegidas por CSRF nas mutações.

## Namespace

```text
app_name = "nursing"
```

## Rotas propostas

| Método | Caminho | View FBV prevista | Capacidade | Observação |
|---|---|---|---|---|
| GET | `/enfermagem/` | `nursing_worklist` | `view_nursing` | encontros acessíveis |
| GET | `/enfermagem/encontros/<uuid:encounter_id>/` | `nursing_encounter` | `view_nursing` | histórico mínimo do encontro |
| GET/POST | `/enfermagem/encontros/<uuid:encounter_id>/sinais-vitais/novo/` | `vitals_create` | `record_vitals` | fluxo online; integra o piloto PWA quando a própria tela perde conexão |
| GET/POST | `/enfermagem/sinais-vitais/<uuid:record_id>/corrigir/` | `vitals_correct` | `record_vitals` | cria novo registro com `replaces`; não edita o original |
| POST | `/enfermagem/sinais-vitais/sincronizar/` | `vitals_sync` | `record_vitals` | sync interno do único `operation_type=nursing.vitals.record`; sessão + CSRF; JSON técnico; não é API pública |
| GET | `/enfermagem/encontros/<uuid:encounter_id>/medicacoes/` | `medication_list` | `administer_medication` | itens dispensados rastreáveis |
| GET/POST | `/enfermagem/medicacoes/<uuid:dispense_item_id>/administrar/` | `medication_administer` | `administer_medication` | network-only |

## Regras comuns

- FBVs por padrão conforme `AGENTS.md`;
- `@login_required` em todas as rotas;
- `@require_GET`/`@require_POST`/`@require_http_methods` conforme necessidade;
- autorização por capacidade + escopo PEP antes de renderizar conteúdo identificável;
- `Cache-Control: private, no-store` nas páginas clínicas e respostas de sync;
- IDs UUID em path; nenhum nome/CPF/medicamento em URL;
- mutações retornam feedback com `django.contrib.messages` após redirect quando online;
- erros de domínio não exibem stacktrace, SQL, medidas clínicas ou PHI.

## Sincronização offline

A sincronização do piloto de sinais vitais usa exclusivamente:

```text
POST /enfermagem/sinais-vitais/sincronizar/
operation_type = nursing.vitals.record
```

A rota é interna ao monólito, autenticada por sessão, protegida por CSRF e não pertence ao namespace público `/api/`. Ela recebe somente o envelope aprovado pela Spec 014 e o payload mínimo da Spec 004, compara o fingerprint com a sessão atual e reaplica `record_vitals`, escopo PEP, estado do `Encounter`, `VitalSignsRecordForm` e `record_vital_signs()`.

Respostas de conflito usam códigos técnicos sem ecoar valores clínicos. Administração de medicamento e qualquer outra mutação permanecem fora da fila offline.
