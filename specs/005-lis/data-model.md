# Modelo implementado — LIS v1

Todos os modelos ficam em `apps.clinical.lis`. UUIDs como PK, `TextChoices` apenas se houver enum real. FKs de registros clínicos usam `PROTECT`.

| Modelo | Campos |
|---|---|
| `LabTest` | id UUID; code CharField(64) unique; name CharField(200); specimen_type CharField(100); active BooleanField default True |
| `ServiceRequest` | id UUID; encounter FK pep.Encounter; lab_test FK LabTest; test_code(64), test_name(200), specimen_type(100) como retrato; requested_by FK User; requested_at auto_now_add; operation_key UUID unique |
| `Specimen` | id UUID; service_request OneToOneField; accession_code CharField(64) unique; collected_at DateTimeField; collected_by FK User; recorded_at auto_now_add; operation_key UUID unique |

`ServiceRequest` e `Specimen` append-only pela aplicação; não registrar edição/exclusão desses modelos no Admin. `LabTest` usa Admin nativo; desativação impede pedidos novos e não altera pedidos/coletas anteriores. Remoção de exame referenciado impedida por PROTECT.

Não duplicar paciente: ele é obtido por `encounter.patient`. Não duplicar estado: situação é derivada da relação com Specimen. Ordenar pedidos por `-requested_at, -id`, com índice correspondente para paginação. Preservar horários com timezone.

Capacidades customizadas em ServiceRequest: `lis.view_orders`, `lis.order_test`, `lis.collect_specimen`. Consulta é pré-requisito das demais; grupos não recebem concessões automáticas. Catálogo usa permissões Django de LabTest.

Representações `__str__` contêm apenas tipo/UUID. Excluir campos textuais sensíveis do auditlog. Leituras registram apenas IDs e ator; nenhuma identificação física da amostra em eventos/logs técnicos.
