# Tarefas — Spec 012 v1

Status: v1 aprovada em 2026-09-16 e implementada. Cada tarefa deve caber em até um dia; dividir novamente se exceder esse limite. Evidências e limites em `validation.md`.

- [x] **T-INT-01:** inventariar dependências e escrever spec/plano/modelo/contratos/aceitação (CA-INT-01–06).
- [x] **T-INT-02:** aprovação explícita recebida do mantenedor: “aprovado, continue”.
- [x] **T-INT-03:** criar app e recibo append-only, capacidade e migration reversível; testar preservação/rollback (CA-INT-01/05).
- [x] **T-INT-04:** implementar serialização mínima e testes de allowlist, UTF-8 e digest (CA-INT-04).
- [x] **T-INT-05:** implementar form/FBV/rota/template com permissões, CSRF e revalidação de escopo; testes HTTP (CA-INT-01–03).
- [x] **T-INT-06:** integrar recibo/auditlog em transação, testar falhas e ausência de PHI nos logs (CA-INT-01/05).
- [x] **T-INT-07:** verificar network-only/no-store, ausência de fila/cache e não ampliação da API pública; regressões (CA-INT-06).
- [x] **T-INT-08:** vincular Gherkin à jornada Playwright, testar download, revogação, mobile e axe (CA-INT-01–06).
- [x] **T-INT-09:** executar gates existentes de CI e registrar resultados/limitações sem marcar testes não executados (todos os critérios).
- [x] **T-INT-10:** documentar piloto sintético, limites do arquivo, guarda e rollback; atualizar rastreabilidade com nomes reais dos testes (todos os critérios).

## Próximos incrementos, ainda sem autorização

- Spec 013: [acompanhamento de solicitações do titular](../013-lgpd-anvisa/spec.md) aprovado e implementado; evidências na respectiva spec. Bases legais, retenção e efeitos automáticos sobre os dados continuam reservados à governança institucional.
- Extensão 012 para HL7/ASTM: contrato de importação, origem confiável, identificação, deduplicação e quarentena antes do LIS.
- Spec 005: pedidos/amostras/resultados após aprovação de suas specs e dependências; valores críticos dependem de regras institucionais.
