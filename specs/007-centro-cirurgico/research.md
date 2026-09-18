# Inventário de reuso — 2026-09-18

Nível 1/2/3 — projeto, Django nativo e funções simples. Nenhuma regra clínica/regulatória externa escolhida nesta etapa.

| Fonte | Reuso concreto |
|---|---|
| apps/clinical/pep/models.py e permissions.py | Encounter/Patient, OPEN, accessible_patients e is_internal_professional |
| apps/clinical/ris/models.py, forms.py, services.py, views.py | Catálogo/retrato, UUID de operação, locks, constraint identificada, Forms/FBVs, falha segura de leitura auditada |
| apps/clinical/ris/tests/ | HTTP/domínio, concorrência PostgreSQL e ausência de N+1 |
| templates/clinical/pep/encounter_detail.html e navbar/navbar.html | Entrada contextual e menu |
| aegis_share/middleware.py | Proteção privada de namespace, inclusive erros/CSRF |
| templates/pwa/service-worker.js | Navegações sem persistência, rotas privadas network-only |
| tests/e2e/ris_journeys.spec.js e prepare_ris_journeys.py | Fixtures sintéticas, retry, isolamento, revogação Admin, mobile/axe e offline |
| .github/workflows/django.yml | Runner/gates existentes, sem dependência nova |
| apps/clinical/adt/models.py | Location/UserLocationAccess disponíveis para contrato futuro de mapa, sem criar sala paralela nesta v1 |
| apps/clinical/prescription/models.py | Estoque de farmácia existente; não duplicar para materiais cirúrgicos sem Spec 009 |

Não usar ImagingOrder/ServiceRequest como solicitação cirúrgica: ownership e retrato específicos. Reusar helpers PEP e padrões Django; não extrair base genérica de pedidos por semelhança entre módulos. Não criar SurgicalSchedule/Material sem operação atual definida.
