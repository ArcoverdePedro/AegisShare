# Contratos propostos — cadastro funcional

Namespace hr; sessão Django e reverse/URLs nomeadas. Consulta institucional de todos os Employee, ativos e inativos.

| Método | Rota | FBV / nome | Template |
|---|---|---|---|
| GET | /rh/funcionarios/ | employee_list | admin/hr/employee_list.html |
| GET | /rh/funcionarios/<uuid:pk>/ | employee_detail | admin/hr/employee_detail.html |

login_required/require_GET; papel interno e hr.view_employee. Lista em 25 por página, page nativo, select_related(user), ordem UUID. Detalhe identifica Employee, não UUID de usuário. Menu RH condicionado à mesma permissão. Sem criar/editar via essas rotas.

Campos apresentados: nome atual (get_full_name com fallback username), username, department, job_title e estado do cadastro. Aviso: “Cadastro funcional informativo — não confirma vínculo, escala ou habilitação”. Nome não é snapshot; perfil inativo/usuário depois reclassificado continua visível ao operador RH autorizado. O usuário titular não recebe acesso automaticamente.

## Manutenção pelo Admin

Django Admin nativo de Employee; URLs derivadas dos nomes admin:hr_employee_changelist/add/change/delete, nunca hardcoded na implementação. Apenas staff interno com hr.view_employee e permissões nativas correspondentes. Visualização também exige papel interno. Exclusão proibida, inclusive bulk action, mesmo com delete_employee. UserAdmin existente permanece separado.

ModelForm do Admin: user ModelChoiceField apenas na criação, queryset de usuários ativos ADM/FUNC sem Employee, label username; department e job_title CharField(120) obrigatórios com trim externo; active Boolean informativo. Na edição, associação somente leitura, identificada por username, sem expor papel/permissões. Não permitir POST adulterado trocar associação. Usuários depois inativos/CLI não impedem edição/desativação do perfil existente.

Salvar explicitamente pelo botão nativo. Sem operation_key/retry customizado ou promessa de histórico append-only para metadados editáveis. Uma segunda tentativa de criar perfil para mesmo usuário não gera duplicata. Unicidade no banco protege corrida entre criações; violação/auditoria falhando não vira sucesso. Não implementar last-write-wins como regra de sincronização; não há sync offline.

## Auditoria, transações e falhas

CREATE/UPDATE Employee com set_actor(request.user), dentro da transação de salvamento Admin que também inclui LogEntry nativo. Não suprimir falha de banco/auditoria; capturar erro operacional após rollback e devolver 503 genérico. Proteção de POST/variáveis sensíveis nas mutações; CSRF nativo.

Nas FBVs, materializar somente página/detalhe e auditar ACCESS em transaction.atomic/set_actor antes da entrega. Usar os mesmos registros auditados no render. Falha reverte o lote de ACCESS e impede conteúdo pessoal. Logs/object_repr não copiam nomes/setor/função. Auditoria do User existente não é alterada.

Fronteira: leituras Admin/lista/formulário/seleção User não emitem ACCESS automaticamente nesta v1; a auditoria de leitura contratada cobre as duas FBVs. Não declarar auditoria integral de leituras administrativas.

Sem sessão: redirect login; papel/capacidade insuficiente: 403; Employee inexistente: 404; método inadequado nas FBVs: 405; falha operacional/auditoria: 503. Namespace RH e rotas EmployeeAdmin private/no-store, Vary Cookie, nosniff, inclusive erros/redirects; campos de RBAC/contato nunca são parte do form Employee.

## PWA, revogação e retirada

Network-only. Offline não confirma mutação Admin nem armazena página, form ou payload privado; sem fila/IndexedDB/push/evento. Revogar hr.view_employee bloqueia consulta e salvamento Admin de formulário já aberto; revogar change_employee bloqueia edição, mantendo consulta quando autorizada. Desativar Employee não desativa login ou permissões do usuário.

Retirada revoga capacidades e preserva perfis/auditoria. Rollback de código preserva dados; reversão de schema só em banco descartável. Uso real exige validação institucional do alcance e da fronteira de auditoria. Nenhum tratamento trabalhista/legal é automatizado.
