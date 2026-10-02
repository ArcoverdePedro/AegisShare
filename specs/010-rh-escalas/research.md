# Inventário pré-implementação — 2026-09-18

Nível 1/2/3: reuso, Django nativo e FBVs. Inventário paralelo somente leitura confirmou as mesmas fronteiras.

| Fonte | Reuso e limite |
|---|---|
| aegis_share/models.py: CustomUser | UUID, AbstractUser, nomes, contatos, ativo, ADM/FUNC/CLI e autenticação já existem; não duplicar |
| aegis_share/admin.py: CustomUserAdmin | Usuário/permissões continuam sob gestão existente; Employee não concede acesso a esse Admin nem altera User |
| apps/clinical/pep/permissions.py | is_internal_professional; accessible_patients não se aplica ao cadastro RH |
| apps/admin/inventory/admin.py | ModelAdmin simples, staff/permissões nativas/papel interno |
| apps/admin/inventory/views.py | FBVs GET, ACCESS em transação, paginação antes de auditar e falha genérica |
| aegis_share/middleware.py | Prefixos privados via reverse; estender para RH e EmployeeAdmin quando implementado |
| templates/navbar/navbar.html | Entrada administrativa condicionada à capacidade |
| templates/pwa/service-worker.js | Network-only existente; sem estender fila offline |
| testes e CI de Specs 007/009 | ModelAdmin, revogação efetiva, mobile/axe/offline, migração e gates |

Busca em apps/aegis_share não encontrou Employee/Shift/TimeClock/Training nem app RH. Uma tabela só agrega setor/função/status cadastral; matrícula, calendário e ponto não têm contrato atual.

Pontos explícitos: Employee.active não é user.is_active; consulta histórica mantém perfil quando usuário muda de papel; identidade usa nome atual, sem snapshot; Admin nativo não gera ACCESS nas suas leituras. Não prometer auditoria administrativa integral nem imutabilidade do banco.

## Resultado

O inventário foi confirmado na implementação de 2026-09-28. Nenhuma dependência, camada de serviço, selector, API ou JavaScript próprio foi necessário.
