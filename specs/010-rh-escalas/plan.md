# Plano — RH v1

Proposta de 2026-09-18; implementar após aprovação do recorte. Nível 1/2/3.

1. App hr, Employee único por User, campos/validação nativa, permissões nativas e migration reversível; auditlog sem setor/função. Não adicionar modelo de setor/cargo ou services/selectors.
2. ModelAdmin pequeno, ModelForm necessário para restrição da associação; papel interno/staff/view/add/change, sem excluir. Associação imutável na edição, sem alterar User/RBAC. Transação nativa, ator explícito e falha operacional genérica após rollback.
3. Duas FBVs GET/DTL com paginação/related queries/ACCESS, menu RH e middleware privado incluindo rotas EmployeeAdmin. Sem pesquisa/filtros/exportações não pedidos.
4. Testar strings obrigatórias/limites/trim, vínculo ativo/interno/único, payload adulterado, perfil após inativação/reclassificação de User, independência de active e preservação dos campos de autenticação/permissões.
5. Testar native Admin permissões/clientes/staff/associação/exclusão, revogação com formulário aberto, rollback CREATE/UPDATE/LogEntry e concorrência PostgreSQL de unicidade. Não declarar retry/controle de versão que não existem no Admin nativo.
6. Testar lista >25, ACCESS só página/detalhe, falha de leitura sem conteúdo pessoal, query related limitada e logs minimizados. Aplicar/reverter/reaplicar migration em banco descartável.
7. Fixture sintética e E2E cadastrar/editar/desativar via Admin/consultar, revogação real, telefone/tablet/axe nas FBVs e forms Admin; offline sem cache/fila. Reusar Playwright/CI.
8. Ruff/check/migrations/suíte/PostgreSQL/Bandit/pip-audit/Lighthouse com evidências/URL/avisos; guia operacional, rastreabilidade e limites de auditoria. Sem afirmar CI remoto/deployment/conformidade/validação institucional sem execução real.
