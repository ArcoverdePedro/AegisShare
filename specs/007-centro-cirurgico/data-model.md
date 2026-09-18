# Modelo implementado — solicitações cirúrgicas

App `apps.clinical.surgery`, label `surgery`. Duas tabelas na migration surgery.0001_initial.

| Modelo | Campos |
|---|---|
| Procedure | id UUID; code CharField(64) unique; name CharField(200); active BooleanField default True |
| SurgicalCase | id UUID; encounter FK pep.Encounter PROTECT; procedure FK Procedure PROTECT; procedure_code CharField(64); procedure_name CharField(200); requested_by FK User PROTECT; requested_at auto_now_add; operation_key UUID com UniqueConstraint uniq_surgery_operation_key |

Procedure ordenado por code; strings não vazias, trim externo, comparação exata de código. SurgicalCase ordenado por -requested_at/-id, índice surgery_requested_idx. Paciente obtido por encounter.patient, sem duplicação. `SurgicalCase` é solicitação, sem estado de realização/autorização/agendamento.

Capacidades customizadas em SurgicalCase: surgery.view_cases e surgery.request_procedure; consulta pré-requisito de criação, sem concessões automáticas a grupos. Catálogo usa permissões nativas do Admin com staff/papel interno. Solicitação sem Admin de edição/exclusão.

Retrato copiado pelo servidor, preservado após mudança do catálogo. __str__ contém somente tipo/UUID. Auditlog exclui code/name e procedure_code/procedure_name; não copia nome de paciente. FKs PROTECT e guardas de mutação das entradas da aplicação preservam histórico, sem garantia contra escrita direta no banco/ORM.
