# Inventário pré-implementação — 2026-09-18

Nível 1/2/3. Contrato de software, sem escolher preços, regras tarifárias ou recomendações financeiras/regulatórias.

| Fonte | Reuso |
|---|---|
| apps/clinical/pep/models.py e permissions.py | Encounter/Patient, accessible_patients e is_internal_professional |
| apps/clinical/adt/models.py | Relação única por Encounter já usada em Admission; conta não depende de internação |
| apps/clinical/ris e surgery | UUID de operação, locks, constraints identificadas, Forms/FBVs e auditoria atômica/falha segura |
| apps/clinical/prescription/models.py e forms.py | DecimalField/checks e validação Forms; sem dispensação/estoque como fonte automática de cobrança |
| Python decimal e Django Sum/F/ExpressionWrapper/DecimalField | Aritmética/agregação exata, sem biblioteca monetária nova |
| aegis_share/middleware.py e templates/pwa/service-worker.js | Namespace privado/network-only |
| navbar e encounter_detail PEP | Navegação/entrada contextual |
| tests/e2e/surgery_journeys.spec.js e CI | Retry, revogação Admin, mobile/axe/offline |

Não existe HospitalAccount/BillingItem. Duas tabelas específicas, sem tarifa/convênio fictício. apps.admin.billing e templates/admin/billing seguem o SDD original; django.contrib.admin continua o Admin do framework. BRL/quantidades inteiras são limites propostos sujeitos a aprovação.

Resultado: recorte autorizado e implementado na mesma data; [evidências](validation.md). O parágrafo anterior registra o estado do inventário inicial.
