# Modelo proposto — cadastro funcional

App apps.admin.hr, label hr; uma tabela. Sem migration nesta proposta.

| Modelo | Campos |
|---|---|
| Employee | id UUID; user OneToOne settings.AUTH_USER_MODEL PROTECT; department CharField(120); job_title CharField(120); active BooleanField default True |

Ordem UUID estável; sem índice adicional além de PK e unicidade do OneToOne. Campos textuais obrigatórios, trim externo; sem enum de setores/cargos inventado. Não duplicar nomes/contatos/segurança. Sem created_by/created_at redundantes: autoria/horário de criação/alteração registrados na auditoria contratada, sem alegação de histórico dos valores textuais excluídos.

Permissões nativas Django: hr.view_employee para consulta, add_employee/change_employee para gestão com view_employee; delete_employee não habilita exclusão nas entradas desta v1. Sem capacidade customizada equivalente ou grants automáticos.

User único, associação imutável na edição Admin; novo vínculo exige usuário ativo ADM/FUNC sem perfil. Perfil existente pode ser atualizado/desativado quando usuário posteriormente fica inativo/CLI, preservando associação. PROTECT impede remover usuário referenciado. Admin não oferece excluir perfil nem ação em lote; escrita direta via ORM/SQL não está abrangida por essa proteção de entrada.

active só informa situação do cadastro. __str__: tipo/UUID. Nome atual e username obtidos de User apenas na apresentação; mudança de nome não altera Employee nem constitui snapshot histórico. auditlog exclui department/job_title; CREATE/UPDATE conservam ator e referência técnica do perfil, sem copiar esses textos.
