# Plano técnico — LIS v1

Status: aprovada em 2026-09-17 e implementada. Evidências em `validation.md`.

Nível usado: **1/2/3 — reuso do monólito, Django nativo e FBVs**.

1. Criar app `apps.clinical.lis` somente após aprovação, com models/forms/views/urls/admin/migration e testes. Reutilizar Encounter, accessible_patients, is_internal_professional, set_actor, accessed, templates Bulma e middleware de privacidade. Sem pacientes, usuários ou auditoria paralelos.
2. Implementar catálogo via Admin. Três modelos e permissões conforme [data-model.md](data-model.md); não criar serviço de terminologia nem popular exames clínicos.
3. FBVs para lista/detalhe/pedido/coleta conforme [contratos](contracts/routes-and-forms.md). Forms cuidam da validação de entrada; operações transacionais em funções específicas se a lógica de lock/retry tornar a view difícil de ler. Nenhuma classe de service ou repository.
4. Aplicar select_related para encontro/paciente/solicitante/coleta/coletor; paginar antes da auditoria de leitura. Auditlog exclui textos sensíveis. Mutações sob transaction.atomic e set_actor. Testar locks e colisões no PostgreSQL.
5. Templates herdam navbar; link Laboratório condicionado à capacidade e ação no encontro conforme permissão. HTML nativo, sem JS adicional ou HTMX sem caso concreto.
6. Estender proteção no-store compartilhada para as rotas LIS. Confirmar comportamento offline sem fila/cache. Nenhum push ou publicação de evento sem consumidor.
7. Testar migration apply → zero → apply em banco descartável. Após uso real, rollback de código preserva tabelas/histórico; não reverter migration para retirar acesso.
8. Executar Ruff, Django check, drift de migration, suíte PostgreSQL, Playwright/axe móvel, Bandit/SCA e Lighthouse existente. Registrar limites, inclusive ausência de categoria Lighthouse PWA atual e CI remoto não executado quando aplicável.
9. Documentar piloto sintético, atribuição de capacidades e catálogo vazio. Uso real exige procedimento institucional e extensões necessárias para exceções/correções.

Sem HL7/ASTM nesta entrega: antes da etapa de resultados, a extensão 012 deve definir origem, versão/perfil, formato de arquivo, correlação pedido/amostra, deduplicação, quarentena e critérios de liberação. Não escolher automaticamente um padrão de equipamento desconhecido.
