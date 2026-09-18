# Modelo implementado — materiais e requisições

App apps.admin.inventory, label inventory. Duas tabelas na migration inventory.0001_initial.

| Modelo | Campos |
|---|---|
| InventoryItem | id UUID; code CharField(64) unique; name CharField(200); unit CharField(40); active BooleanField default True |
| Requisition | id UUID; item FK InventoryItem PROTECT; item_code CharField(64); item_name CharField(200); item_unit CharField(40); quantity PositiveIntegerField; requested_by FK User PROTECT; requested_at auto_now_add; operation_key UUID |

InventoryItem: ordem code, trim externo e strings não vazias em validação nativa/model form. Admin nativo para CRUD, com staff/permissão de modelo/papel interno; exclusão referenciada bloqueada por PROTECT, desativação preserva histórico.

Requisition: ordem -requested_at/-id; índice inventory_req_created_idx; UniqueConstraint uniq_inventory_req_operation; CheckConstraint inventory_req_qty_range para 1–999999. Snapshots exclusivamente do material sob lock. Sem estado, paciente, fornecedor, estoque disponível ou preço.

Capacidades customizadas de Requisition: inventory.view_requisitions e inventory.request_material. Sem concessões automáticas. Auditoria registrada nos dois modelos, excluindo code/name/unit e snapshots/quantity. __str__ retorna tipo/UUID; labels de seleção explícitos no form. Entradas da aplicação impedem atualizar/excluir requisição; não alegar imutabilidade contra SQL/ORM direto.
