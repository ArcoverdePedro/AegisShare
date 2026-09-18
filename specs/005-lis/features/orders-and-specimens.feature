# language: pt
Funcionalidade: Pedidos laboratoriais e coleta manual rastreável
  # Cobertura: apps/clinical/lis/tests/ e tests/e2e/lis_journeys.spec.js.

  Cenário: CA-LIS-01 Solicitar exame ativo para encontro acessível
    Dado um profissional com capacidade de consulta e solicitação
    E um encontro aberto de paciente acessível no PEP e um exame institucional ativo
    Quando submete o pedido
    Então o pedido preserva código, nome e material do exame, encontro, autor e horário
    E não cria resultado, laudo ou concessão de acesso

  Cenário: CA-LIS-02 Registrar coleta confirmada
    Dado um pedido acessível sem amostra e encontro aberto
    Quando o profissional autorizado confirma a conferência e informa código único e horário válido
    Então uma amostra fica vinculada ao pedido com ator e horário de registro
    E a situação exibida é Coleta registrada
    Mas data futura, anterior ao pedido ou confirmação ausente não grava coleta

  Cenário: CA-LIS-03 Revogação e fechamento entre GET e POST
    Dado um formulário aberto por profissional autorizado
    Quando perde capacidade ou escopo ou o encontro é encerrado antes do POST
    Então o servidor nega a operação sem gravar nem revelar dados fora do escopo

  Cenário: CA-LIS-04 Histórico preservado e lista limitada
    Dado pedidos de pacientes acessíveis e não acessíveis
    Quando consulta a lista e o detalhe
    Então somente pedidos autorizados são apresentados e auditados
    E a lista tem até 25 registros por página sem N+1 de consultas relacionadas
    E alterações posteriores do catálogo não mudam o retrato do pedido

  Cenário: CA-LIS-05 Reenvio e concorrência
    Dado uma operação já registrada e autorização ainda válida
    Quando reenvia a mesma chave com conteúdo normalizado equivalente
    Então recebe o registro original sem duplicação
    Mas chave com conteúdo diferente retorna conflito sem sobrescrever dados
    E duas coletas concorrentes diferentes para o mesmo pedido criam no máximo uma amostra

  Cenário: CA-LIS-06 Falha de auditoria reverte a escrita
    Dado uma solicitação ou coleta válida
    Quando a persistência da auditoria falha
    Então a operação é revertida e retorna erro genérico
    E logs e auditlog não copiam nome do paciente, exame, material ou código da amostra

  Cenário: CA-LIS-07 Fronteira online e interface acessível
    Dado um profissional usando telefone ou tablet
    Quando abre os formulários e perde a conexão
    Então nenhuma confirmação falsa ou operação na fila offline é criada
    E dados laboratoriais não são armazenados em cache
    E as respostas online são no-store inclusive erros e CSRF
    E os controles têm labels e não há overflow ou violações axe sérias ou críticas
