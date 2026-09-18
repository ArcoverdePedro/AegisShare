# language: pt
Funcionalidade: Solicitar material sem confirmar estoque ou compra
  # Critérios cobertos por testes HTTP/PostgreSQL/Playwright mapeados em validation.md.

  Cenário: CA-INV-01 Catálogo institucional
    Dado catálogo não medicamentoso mantido por staff interno com permissões de modelo
    Quando consulta o catálogo com capacidade de consulta
    Então vê somente materiais ativos com código, nome e unidade
    E código único e textos obrigatórios são validados
    E não há saldo fictício ou mudança do estoque farmacêutico

  Cenário: CA-INV-02 Capacidades e alcance
    Dado consulta institucional explicitamente autorizada por este contrato
    Então operador interno com capacidade vê requisições de outros autores
    Mas cliente, papel ADM sem capacidade e usuário sem sessão não obtêm acesso equivalente
    E revogação de capacidade bloqueia POST de formulário já aberto

  Cenário: CA-INV-03 Requisição e validação
    Quando confirma material ativo e quantidade inteira entre 1 e 999999
    Então recebe registro com snapshot, autor e horário do servidor
    Mas fração, zero, negativo, excesso, UUID inválido ou falta de confirmação são rejeitados
    E catálogo inativo impede operação nova
    E não há reserva, compra, entrega ou evento automático

  Cenário: CA-INV-04 Retry e concorrência
    Quando operações equivalentes chegam simultaneamente no PostgreSQL
    Então retornam o mesmo registro sem duplicar mantendo autoria e snapshots
    E retry após renomeação ou desativação preserva o retrato original
    E chave nova cria requisição distinta
    Mas colisão entre atores, quantidades ou materiais retorna conflito sem revelar original

  Cenário: CA-INV-05 História e paginação
    Dado mais de 25 requisições e catálogo posteriormente alterado
    Quando consulta lista e detalhe
    Então renderiza snapshots históricos e só 25 requisições por página
    E audita somente registros renderizados sem queries por registro

  Cenário: CA-INV-06 Auditoria e preservação
    Quando auditoria de criação falha
    Então criação é revertida
    E auditoria de leitura falhando impede entrega de conteúdo
    E requisições não têm edição ou exclusão nas entradas da aplicação
    E catálogo referenciado não pode ser excluído
    E logs não copiam textos ou quantidades e nenhuma falha é convertida em sucesso

  Cenário: CA-INV-07 HTTP e dispositivos
    Quando usa rotas sem CSRF ou com método inadequado
    Então a operação é impedida com headers de privacidade
    E telefone e tablet não têm overflow ou violações axe sérias ou críticas
    E offline não confirma nem armazena formulário, payload ou página privada
