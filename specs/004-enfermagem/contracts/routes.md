# Contrato — Rotas da Enfermagem

Nenhuma rota REST pública é criada. Todas as superfícies são Django server-rendered, autenticadas por sessão e protegidas por CSRF nas mutações.

## Namespace

```text
app_name = "nursing"
```

## Rotas propostas

| Método | Caminho | View FBV prevista | Capacidade | Observação |
|---|---|---|---|---|
| GET | `/enfermagem/` | `nursing_worklist` | `view_nursing` | encontros acessíveis |
| GET | `/enfermagem/encontros/<uuid:encounter_id>/` | `nursing_encounter` | `view_nursing` | histórico mínimo do encontro |
| GET/POST | `/enfermagem/encontros/<uuid:encounter_id>/sinais-vitais/novo/` | `vitals_create` | `record_vitals` | fluxo online; pode integrar fila PWA no cliente |
| GET/POST | `/enfermagem/sinais-vitais/<uuid:record_id>/corrigir/` | `vitals_correct` | `record_vitals` | cria novo registro com `replaces`; não edita o original |
| GET | `/enfermagem/encontros/<uuid:encounter_id>/medicacoes/` | `medication_list` | `administer_medication` | itens dispensados rastreáveis |
| GET/POST | `/enfermagem/medicacoes/<uuid:dispense_item_id>/administrar/` | `medication_administer` | `administer_medication` | network-only |

## Regras comuns

- FBVs por padrão conforme `AGENTS.md`;
- `@login_required` em todas as rotas;
- `@require_GET`/`@require_POST`/`@require_http_methods` conforme necessidade;
- autorização por capacidade + escopo PEP antes de renderizar conteúdo identificável;
- `Cache-Control: private, no-store` nas páginas clínicas;
- IDs UUID em path; nenhum nome/CPF/medicamento em URL;
- mutações retornam feedback com `django.contrib.messages` após redirect quando online;
- erros de domínio não exibem stacktrace, SQL ou PHI.

## Sincronização offline

A sincronização do piloto de sinais vitais **não cria uma API REST pública**. A implementação deve usar uma rota interna autenticada por sessão/CSRF ou mecanismo interno já compatível com a PWA, explicitamente restrito ao contrato `nursing.vitals.record`.

Antes de implementar, a rota concreta de sync deve ser incluída neste contrato e no teste arquitetural que diferencia superfície interna autenticada de API pública. Nenhuma rota genérica `/api/` é autorizada por esta spec.
