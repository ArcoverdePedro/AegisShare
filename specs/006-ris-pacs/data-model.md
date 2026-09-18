# Modelo implementado — RIS v1

App `apps.clinical.ris`, label `ris`. Duas tabelas na migration ris.0001_initial.

| Modelo | Campos |
|---|---|
| ImagingExam | id UUID; code CharField(64) unique; name CharField(200); active BooleanField default True |
| ImagingOrder | id UUID; encounter FK pep.Encounter PROTECT; exam FK ImagingExam PROTECT; exam_code CharField(64); exam_name CharField(200); requested_by FK User PROTECT; requested_at auto_now_add; operation_key UUID com UniqueConstraint uniq_ris_operation_key |

Catálogo ordenado por código. Retirar espaços externos de código/nome antes da validação; strings vazias proibidas. Comparação de código exata/sensível a maiúsculas. Não usar identificadores de paciente no catálogo. Catálogo usa permissões nativas do Django; alteração posterior não muda snapshots.

Pedidos ordenados por `-requested_at, -id`, com índice correspondente para paginação. Paciente obtido por `encounter.patient`; sem FK redundante. Sem campo status, modalidade, prioridade, indicação, estudo, laudo ou resultado.

Capacidades customizadas em ImagingOrder: `ris.view_orders`, `ris.order_exam`. Consulta é pré-requisito para criar. Nenhuma associação automática a grupos/roles; Admin de catálogo exige permissões nativas, staff e papel interno. Pedidos sem registro no Admin.

`__str__` de ambas as entidades contém apenas tipo/UUID, para não copiar conteúdo para auditoria. Excluir `code`, `name`, `exam_code`, `exam_name` dos respectivos registros genéricos de auditlog. Registrar CREATE/UPDATE de catálogo e CREATE/ACCESS de pedidos com ator.

`operation_key` identifica operação, não exame/paciente. Unicidade protege retries; uma nova chave autoriza um pedido distinto somente após as mesmas validações. Pedidos imutáveis nas entradas da aplicação; alterações/deleções rejeitadas, sem promessa de imutabilidade física do banco.
