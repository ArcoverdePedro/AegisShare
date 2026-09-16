# Plano técnico — Spec 013 v1

Status: v1 aprovada em 2026-09-16 e implementada; evidências em `validation.md`.

## Arquitetura

Nível usado: **1/2/3 — reuso do projeto + Django nativo + FBV**.

`apps/compliance` implementado com models, forms, views, urls, migrations e testes. Reusar `Patient`, `accessible_patients`, `is_internal_professional`, sessão/CSRF, `set_actor` e `accessed`. Não criar cadastro de titulares paralelo, repository, motor de políticas ou módulo genérico de workflow.

## Modelo de Dados

`DataSubjectRequest` guarda o cadastro e estado atual; `DataSubjectRequestEvent` guarda o histórico append-only. Especificação em `data-model.md`.

Manter o estado atual permite filtrar/paginar sem calcular o último evento de cada linha; sua consistência com os eventos é garantida por transação, constraint de unicidade e testes. Nenhuma edição genérica via admin é registrada.

## Rotas e Views

FBVs com `@login_required`, restrição de método e verificação explícita das capacidades. Querysets de solicitação são filtrados por `patient__in=accessible_patients(user)` antes do lookup. Fora do escopo: 404. Ausência da capacidade: 403. Sem sessão: redirect ao login.

Lista: 25 itens por página; `select_related("patient", "created_by")`. Detalhe: solicitação e eventos com ator via `select_related`. Auditar somente solicitações da página apresentada e a solicitação aberta no detalhe, sem copiar notas para auditoria.

## Formulários e Validação

`DataSubjectRequestForm` é ModelForm para paciente, categoria e resumo. `RequestTransitionForm` é Form de operação, com estado esperado, destino e nota. Contrato em `contracts/forms.md`. Validar novamente a transição após adquirir o lock; um form válido não substitui o estado atual no banco.

## Transações e concorrência

- Criação: revalidar paciente acessível, gravar solicitação e evento RECEIVED sob `transaction.atomic()` + ator auditável.
- Transição: localizar solicitação autorizada, bloquear a linha de `DataSubjectRequest` via `select_for_update()`, revalidar acesso, comparar estado esperado e validar o único próximo estado permitido; atualizar estado e inserir evento na mesma transação.
- Lock deve abranger somente a solicitação, evitando bloquear linhas de paciente/ator por joins desnecessários.
- Retry após resposta perdida recebe 409 com orientação de consultar o histórico; não repetir o evento nem fingir nova transição.
- A criação de duas solicitações distintas não é deduplicada por nome, categoria ou texto; não inferir equivalência entre pedidos administrativos.

O fluxo de transição cabe inicialmente na própria FBV; extrair função específica somente se clareza ou reutilização real exigir. Nenhuma operação externa é feita dentro da transação.

## Templates e componentes HTMX

Reusar layout e estilo atuais. HTML nativo com POST/redirect/GET e mensagens Django. Nenhum componente HTMX ou JavaScript próprio é necessário. Link no menu condicionado à permissão de consulta; botões de ação condicionados também à capacidade específica, sem substituir a autorização do servidor.

## Eventos internos

`contracts/events.md` define eventos persistidos e auditoria. Nenhum consumidor exige WebSocket/Celery nesta v1; não criar canais AsyncAPI sem uso concreto.

## PWA e segurança

`/lgpd/` network-only pelo service worker existente. Garantir `private, no-store`, `Vary: Cookie` e `nosniff` em HTML, redirects e erros, inclusive CSRF. O middleware compartilhado `aegis_share.middleware.PrivateWorkflowMiddleware` cobre a exportação da Spec 012 e as rotas deste módulo, inclusive respostas antecipadas.

Não inserir payload na fila offline, notificações ou push. Excluir resumo/nota do auditlog; aplicar redaction de POST em relatórios de erro e respostas genéricas a falhas de banco. Nenhum estado altera autorização PEP, exporta ou elimina dados.

## Migrações

Migration inicial com duas tabelas, permissões e FKs PROTECT. Constraint única por solicitação/estado de destino impede eventos repetidos na sequência irreversível desta v1. Testar ida/volta em banco descartável. Após uso real, rollback de código preserva tabelas/histórico.

## Testes

Runner Django e Playwright existentes; não instalar pytest-bdd adicional. Testar criação com evento inicial, transições, nota de encerramento, revogação entre GET/POST, ausência de PHI nos erros/logs, falha atômica, texto escapado e número de queries independente do tamanho da página.

Concorrência exige PostgreSQL: dois POSTs sobre o mesmo estado produzem uma transição e um conflito, nunca dois eventos. SQLite não valida lock de linha; marcar essa diferença nas evidências.

## Rollout

Aprovar → implementar → migration/permissões → testes → piloto sintético → procedimento institucional para uso real. Capacidades não são atribuídas automaticamente. Operação de atendimento não desbloqueia consentimentos, retenção, expurgo ou direitos automatizados.
