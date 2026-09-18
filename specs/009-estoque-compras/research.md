# Inventário pré-implementação — 2026-09-18

Nível 1/2/3: reuso do projeto, Django nativo e FBVs.

| Fonte lida | Reuso e fronteira |
|---|---|
| apps/clinical/prescription/models.py | StockItem, Lot e StockMovement já atendem medicamentos; não duplicar nem alterar |
| apps/clinical/prescription/stock_services.py | Entradas/ajustes/saldos farmacêuticos já têm transações; não chamar para requisição de material |
| apps/clinical/surgery/models.py, forms.py, services.py e admin.py | Catálogo ativo, snapshots, Admin restrito, operação UUID, lock e constraint identificada |
| apps/admin/billing/models.py | Limites inteiros, confirmação, capacidades explícitas e guardas append-only |
| apps/clinical/pep/permissions.py | is_internal_professional; accessible_patients não se aplica a registros sem paciente |
| aegis_share/middleware.py | Namespace privado com reverse; incluir /estoque/ quando implementado |
| templates/navbar/navbar.html e templates/pwa/service-worker.js | Navegação administrativa e estratégia atual network-only |
| testes/CI das Specs 007/008 | PostgreSQL concorrente, auditoria, mobile/axe/offline e gates existentes |

Busca em apps não encontrou InventoryItem, Supplier, PurchaseOrder ou Requisition de materiais gerais. Não criar esses quatro modelos de uma vez: o caso atual proposto precisa apenas de InventoryItem e Requisition. Fornecedores/compras/saldos ficam em extensões com regras reais.

Resultado: recorte autorizado e implementado na mesma data. [Evidências](validation.md); o inventário acima registra as fronteiras identificadas antes da implementação.
