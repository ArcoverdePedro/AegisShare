# Tarefas — RIS v1

Aprovada e implementada em 2026-09-18; [evidências](validation.md). Tarefas de até um dia; dividir se exceder. Conclusão significa somente trabalho local efetivamente validado.

- [x] **T-RIS-01:** inventariar PEP/LIS/Core/PWA e preparar recorte, modelo, contratos, plano e aceitação. CA-01–07.
- [x] **T-RIS-02:** aprovação explícita do recorte de pedidos e sequenciamento RIS/PACS. CA-01–07.
- [x] **T-RIS-03:** app, models, permissões, Admin e migration reversível. CA-01/05/06.
- [x] **T-RIS-04:** form, FBVs, URLs, templates, paginação e entrada pelo encontro. CA-01–04.
- [x] **T-RIS-05:** locks/retries/constraints e concorrência PostgreSQL. CA-03/05.
- [x] **T-RIS-06:** auditoria, rollback, privacidade de erros e minimização de logs. CA-02/04/06.
- [x] **T-RIS-07:** jornadas E2E, mobile/tablet/axe e offline sem persistência. CA-01/02/05/07.
- [x] **T-RIS-08:** gates locais, guia operacional, evidências e rastreabilidade executável. CA-01–07.

## Gates posteriores, sem autorização de implementação

- **PACS:** nó real, protocolo/configuração, identidade, correlação e armazenamento/retenção/recuperação definidos antes de DICOM/viewer.
- **Laudos:** modelo clínico, estados e contrato jurídico/operacional de assinatura antes de Report/liberação.
- **Eventos:** consumidor e contrato mínimo de imaging.order.created antes de publicar.

## Continuidade independente do roadmap

[Spec 007 — solicitações de procedimentos](../007-centro-cirurgico/spec.md), autorizada e implementada em 2026-09-18; [evidências](../007-centro-cirurgico/validation.md). Preserva os gates de PACS/laudos e não publica eventos de execução cirúrgica.
