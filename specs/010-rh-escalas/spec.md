# Spec 010 — RH e Escalas v1: cadastro funcional mínimo

## Status

**Proposta de 2026-09-18, aguardando aprovação explícita. Não implementada.** Autorizações anteriores cobrem os respectivos recortes, sem aprovar automaticamente este módulo.

## Recorte e histórias

A fase 4 continua pelo cadastro funcional de usuários internos existentes. Employee acrescenta somente setor, função e active informativo ao CustomUser. Não cria usuário, contrato, admissão, escala, jornada, pagamento, habilitação clínica ou certificação de treinamento.

Como operador de RH autorizado, quero manter um perfil por profissional pelo Admin e consultar setor/função sem duplicar a identidade. Como auditor, quero identificar criação/alteração e as consultas da interface de RH sem copiar nomes, setores e funções para logs genéricos.

Propõe-se **consulta institucional de todos os perfis**, incluindo desativados, por capacidade explícita hr.view_employee. Não há escopo por setor ou autoacesso do titular nesta v1. O alcance e os três campos novos dependem da aprovação deste recorte. Piloto sintético até validação institucional de finalidade, acesso e conteúdo dos campos.

## Requisitos funcionais

- **RF-HR-01:** Employee com UUID, user OneToOne PROTECT para CustomUser, department e job_title obrigatórios até 120 caracteres cada, trim externo, e active default True. Não duplicar nome, username, contato, CPF, senha ou RBAC. Não criar matrícula sem caso atual. Identidade exibida vem de user.get_full_name() com fallback username; username identifica a associação quando necessário.
- **RF-HR-02:** manutenção pelo Django Admin nativo, com staff, papel interno, hr.view_employee e a permissão nativa add_employee/change_employee correspondente. Novo vínculo exige usuário ativo ADM/FUNC e ausência de perfil; seleção identifica por username, sem campos de contato/RBAC. Usuário associado fica somente leitura na edição. Exclusão não permitida, inclusive ação em lote. Desativação preserva perfil/auditoria.
- **RF-HR-03:** active é marcador cadastral; nunca altera user.is_active, nivel_permissao, is_staff, is_superuser, grupos, capacidades, grants PEP ou outros módulos. Alterações posteriores do usuário não apagam perfil nem obrigam troca de associação. Consultas autorizadas conservam perfis de usuários depois inativados/reclassificados; nomes são atuais, sem snapshot histórico ou afirmação de vínculo empregatício.
- **RF-HR-04:** duas FBVs GET, sessão, is_internal_professional e hr.view_employee. Papel ADM não substitui permissão; superusuário segue Django com requisito interno. Sem concessões automáticas. Ter perfil não autoriza consulta RH, gestão Admin, paciente ou atos clínicos.
- **RF-HR-05:** lista de todos os perfis, ativos/inativos, paginada em 25; detalhe por UUID Employee. select_related(user), ordem estável UUID, sem query por perfil. Menu RH somente para interno com hr.view_employee. Exibir nome atual/username, setor, função e estado do cadastro; omitir contatos, papéis de segurança e dados trabalhistas inexistentes. Não listar todos os usuários sem Employee como se fossem funcionários cadastrados.
- **RF-HR-06:** auditlog Employee para CREATE/UPDATE com ator do request; excluir department/job_title, __str__ apenas tipo/UUID. Admin LogEntry nativo identifica mudanças, sem duplicar valores de campos em object_repr. Nas duas FBVs, ACCESS apenas perfis efetivamente renderizados; falha de auditoria impede entrega e reverte o lote de ACCESS. Criação/alteração e auditoria/Admin LogEntry atômicos; falha não confirma alteração parcial.
- **RF-HR-07:** validação por ModelForm/Admin e model.clean; unicidade OneToOne garantida no banco para concorrência. Admin não transforma violação concorrente/auditoria em sucesso: resposta operacional genérica após rollback. Associação imutável e exclusão proibida nas entradas contratadas; sem alegação de imutabilidade contra ORM/SQL direto.

## Fronteira de auditoria

ACCESS cobre as duas páginas de consulta RH. O Admin nativo audita **criação/alteração**, não emite ACCESS automaticamente em leituras de lista/formulário ou da seleção de usuários. Essa fronteira é explícita nesta proposta; não se declara auditoria de toda leitura administrativa ou conformidade integral. Caso a instituição exija ACCESS de todas essas leituras, o contrato deve ser estendido antes desse uso. Não alterar auditoria global de CustomUser nesta v1.

## Requisitos não funcionais

- **RNF-HR-01:** apps.admin.hr, label hr, uma tabela. Django Admin/ModelForm e duas FBVs/DTL; reutilizar CustomUser, papel interno, auditlog, layout, middleware e CI. Sem service/selector/repository novo, classe de serviço, JS próprio, dependência ou API REST pública.
- **RNF-HR-02:** /rh/funcionarios/ e rotas do EmployeeAdmin private/no-store, Vary Cookie, nosniff, inclusive erros/redirects; proteção de POST/variáveis sensíveis nas mutações Admin. CSRF nativo. Falha de banco/auditoria 503 genérico, sem traceback/valores internos; 403 sem capacidade, 404 registro inexistente, 405 método incompatível nas FBVs.
- **RNF-HR-03:** online apenas; sem Cache Storage/IndexedDB de cadastro/páginas, fila, sync, push ou eventos sem consumidor. Telefone/tablet sem overflow, labels acessíveis, axe sem violações sérias/críticas nas páginas RH e formulários de manutenção.
- **RNF-HR-04:** migration versionada/reversível, checks/lint/testes/Admin/PostgreSQL/rollback/E2E/SAST/SCA com evidências. Lighthouse registra URL/pontuações/avisos reais; execução bem-sucedida não significa meta 90 atingida.

## Fora de escopo e gates posteriores

Shift, TimeClock, Training, escalas/calendário, conflito de horários, jornada, horas extras/banco de horas, ponto/biometria/geolocalização, folha/remuneração/contratos, documentos de pessoal, matrícula, admissões/desligamentos, habilitação profissional e bloqueio clínico por treinamento.

Escalas/ponto exigem contrato de setor, horário/fuso, conflito, alterações, autoria e validação institucional das regras reais. Capacitação exige catálogo, critérios de conclusão, validade e efeitos aprovados. Não emitir shift.created/timeclock.recorded/training.completed sem fato persistido e consumidor contratado. Nenhuma decisão trabalhista ou clínica automática.

## Rastreabilidade planejada

| Requisito | Superfície | Template | Critério/teste futuro |
|---|---|---|---|
| 01/02/07 | EmployeeAdmin add/change | Admin nativo | CA-HR-01, CA-HR-02, CA-HR-06 |
| 03/04 | Admin e duas FBVs | Admin + templates RH | CA-HR-03, CA-HR-04 |
| 04/05/06 | employee_list | admin/hr/employee_list.html | CA-HR-04, CA-HR-05, CA-HR-06 |
| 04/05/06 | employee_detail | admin/hr/employee_detail.html | CA-HR-04, CA-HR-05, CA-HR-06 |
| RNF-02/03/04 | middleware/Admin/PWA/CI | layout existente | CA-HR-07 |

[Inventário](research.md), [modelo](data-model.md), [contratos](contracts/routes-and-forms.md), [plano](plan.md), [tarefas](tasks.md), [aceitação](features/employees.feature). Critérios planejados; sem testes executáveis/evidências de implementação desta spec.

## Definition of Done

- [x] Inventário, recorte, modelo, contratos, plano, tarefas e aceitação.
- [ ] Aprovação: três campos funcionais, consulta institucional incluindo inativos, manutenção pelo Admin e fronteira de auditoria.
- [ ] App/model/Admin/FBVs/migration/privacidade.
- [ ] Permissões/validação/isolamento de RBAC/auditoria/rollback/concorrência testados.
- [ ] E2E/revogação/mobile/tablet/axe/offline/gates com evidências e guia.
- [ ] Validação institucional antes do uso real.
