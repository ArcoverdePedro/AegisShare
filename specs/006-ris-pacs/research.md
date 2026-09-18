# Inventário de reuso — 2026-09-18

Nível 1/2/3: reutilizar primeiro o projeto, Django nativo e funções simples. Apenas leitura de código nesta etapa, sem consultar informações clínicas/regulatórias externas nem escolher regras clínicas.

| Fonte existente | Reuso concreto |
|---|---|
| apps/clinical/pep/models.py | Encounter/Patient canônicos; status OPEN e vínculos existentes |
| apps/clinical/pep/permissions.py | is_internal_professional e accessible_patients; não inventar novo escopo |
| apps/clinical/lis/models.py, forms.py, services.py, views.py | Padrão de catálogo/snapshot, UUID de operação, locks, Forms e FBVs |
| apps/clinical/lis/tests/test_concurrency.py | Teste real de retries concorrentes no PostgreSQL |
| aegis_share/middleware.py | PrivateWorkflowMiddleware, incluindo redirects/erros |
| apps/interoperability e caixa laboratorial | Fronteira de arquivos de laboratório; não usar como transporte de imagem |
| templates/clinical/pep/encounter_detail.html e navbar/navbar.html | Entrada contextual e navegação existente |
| tests/e2e/lis_journeys.spec.js | Jornadas, mobile/axe e inspeção de persistência offline |
| .github/workflows/django.yml | Gates e preparação de fixtures sintéticas já existentes |
| apps/clinical/events.py | send_after_commit disponível para extensão futura com consumidor; sem evento novo nesta v1 |

Não reutilizar LabTest/ServiceRequest como registros de imagem: são entidades laboratoriais, incluindo material/coleta. Duas tabelas específicas mantêm ownership e snapshots sem mudar o LIS. Não extrair framework/base genérica de pedidos: o fluxo RIS é menor e não tem coleta. Reutilizar os helpers PEP e padrões Django já compartilhados.

DICOM, armazenamento de imagem e assinatura de laudos não têm contrato institucional neste recorte. A ausência desses contratos bloqueia suas extensões, não o preparo desta proposta de pedidos.
