# Tarefas — LIS v1

Status: aprovada em 2026-09-17 pela instrução “aprovado, implemente”; implementação e validações locais concluídas; evidências e limites em `validation.md`. Cada tarefa limitada a até um dia; dividir quando necessário.

- [x] T-LIS-01: inventariar PEP, interoperabilidade, auditoria e PWA; preparar spec, plano, modelo e contratos. CA-01–07.
- [x] T-LIS-02: aprovação explícita deste recorte e do sequenciamento de ingestão/resultados. CA-01–07.
- [x] T-LIS-03: models, Admin do catálogo, permissões e migration reversível. CA-01/02.
- [x] T-LIS-04: forms/FBVs/templates de pedidos, lista/detalhe e integração ao encontro. CA-01/03/04.
- [x] T-LIS-05: coleta, confirmação, validação temporal e unicidade. CA-02/03.
- [x] T-LIS-06: locks, retry equivalente, conflito e testes concorrentes PostgreSQL. CA-05.
- [x] T-LIS-07: auditoria minimizada, falha atômica e cabeçalhos sensíveis. CA-06/07.
- [x] T-LIS-08: jornadas E2E, offline, mobile/tablet e axe. CA-01–07.
- [x] T-LIS-09: gates locais, evidências reais, guia operacional e rastreabilidade. CA-01–07.

## Etapa seguinte

Extensão 012 para ingestão por arquivo antes de resultados LIS. Primeiro recorte implementado: [recebimento cifrado em quarentena](../012-interoperabilidade/extensions/lab-inbox/spec.md), aprovado em 2026-09-18 e sem interpretação clínica. Perfil real de equipamento e semântica institucional de correção/recoleta/valores críticos devem ser definidos antes das respectivas implementações.

Continuidade independente do roadmap: [Spec 006 — pedidos de imagem](../006-ris-pacs/spec.md), aprovada e implementada em 2026-09-18; [evidências](../006-ris-pacs/validation.md). Não remove os gates de parsing/resultados LIS.
