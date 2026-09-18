# Materiais e requisições internas — Spec 009 v1

Nível 1/2/3: reuso do projeto, Django nativo e FBVs. Catálogo institucional de materiais não medicamentosos; requisições internas de uma linha. Não confirma disponibilidade, reserva, compra, entrega ou consumo. O estoque farmacêutico da Spec 003 permanece separado.

## Ativação e permissões

Aplicar a migration `inventory.0001_initial` pelo procedimento de atualização existente. Conceder explicitamente `inventory.view_requisitions` a profissionais internos que possam consultar **todos** os registros deste módulo. Para registrar, conceder também `inventory.request_material`. Papel ADM não substitui capacidade; superusuário segue Django com requisito de papel interno. Não há concessões automáticas.

Gestão do catálogo no Django Admin: usuário staff interno com permissões nativas de InventoryItem. Cadastrar código único, nome, unidade de contagem e ativo. Código distingue maiúsculas/minúsculas; espaços externos são removidos. Definir unidades reais e coerentes (ex.: caixa), sem conversão automática de embalagens. O sistema não classifica medicamentos automaticamente: a instituição deve manter apenas materiais não medicamentosos nesse catálogo. Não cadastrar identificação de paciente ou conteúdo clínico.

Piloto sintético até validação institucional das unidades, do catálogo e do alcance de consulta. Esta versão não implementa segregação por setor/almoxarifado; não utilizá-la em fluxos que dependam desse controle sem uma extensão aprovada.

## Uso

Menu **Estoque** abre o catálogo ativo, paginado em 25 materiais. **Requisições internas** consulta registros de todos os autores autorizados, também em páginas de 25. **Requisitar material** seleciona um material ativo, quantidade inteira de 1 a 999999 e confirmação obrigatória. Cada registro representa um material; duas necessidades são dois registros.

Código/nome/unidade são copiados pelo servidor. Alteração ou desativação posterior do catálogo não altera o histórico. Requisição não possui edição/exclusão/atendimento/cancelamento neste recorte. Material referenciado não pode ser excluído; desativação é o caminho para retirá-lo de novas solicitações.

O seletor HTML carrega o catálogo ativo inteiro, embora a página do catálogo seja paginada. Se o volume tornar a seleção impraticável, aprovar busca/paginação do seletor; não há JavaScript próprio ou componente adicional nesta v1.

## Reenvios e falhas

Cada formulário recebe UUID de operação. Reenvio de mesma chave, autor, material e quantidade retorna a requisição original, mantendo horário e snapshots, mesmo após desativação/renomeação. Nova chave cria registro distinto, inclusive com conteúdo igual. Não usar um formulário novo para reconhecer um envio já concluído: consultar o histórico primeiro.

Confirmação também é exigida no retry. Dados inválidos preservam a chave. Conflito retorna 409 genérico sem revelar registro original. Falha operacional/auditoria retorna 503; consultar histórico antes de tentar novamente. Retirada de capacidade bloqueia POST de formulário já aberto, inclusive retry.

Criação e auditoria são atômicas; falha reverte criação. Consultas geram ACCESS apenas para registros renderizados. O formulário audita todos os materiais que apresenta no seletor e renderiza essas mesmas escolhas. Auditlog não copia textos ou quantidades; requisições aparecem por UUID nos logs genéricos.

## Online e retirada

Todas as rotas /estoque/ exigem sessão e capacidades, CSRF nos POSTs e respostas private/no-store, Vary Cookie e nosniff, inclusive erros/redirects. Fluxo somente online: offline não confirma envio nem mantém payload/página privada em fila, Cache Storage ou IndexedDB. Sem push, sincronização ou evento automático.

Para retirar, revogar capacidades e impedir novos registros preservando catálogo, requisições e auditoria. Rollback de código conserva dados. Reverter schema somente em banco descartável; rollback em ambiente com dados exige procedimento de preservação previamente definido. Guardas append-only e PROTECT protegem as entradas da aplicação, não escrita direta no banco/ORM.

## Extensões posteriores

Saldos/lotes/movimentos precisam de contratos de unidade/localização/validade/ajuste e concorrência. Fornecedores/compras/recebimento precisam de autorização e regras operacionais próprias. Integração farmacêutica exige fonte de verdade explícita; esta v1 não muda StockItem, Lot, StockMovement, dispensação ou faturamento.

[Spec e critérios](../specs/009-estoque-compras/spec.md) · [Evidências executadas](../specs/009-estoque-compras/validation.md).
