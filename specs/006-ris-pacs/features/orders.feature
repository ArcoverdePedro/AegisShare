# language: pt
Funcionalidade: Solicitar imagem sem criar estudos ou laudos
  # Evidências e rastreabilidade executável em ../validation.md.

  Cenário: CA-RIS-01 Pedido para encontro acessível
    Dado um profissional com consulta e criação RIS e acesso PEP ao paciente
    E um encontro aberto e exame ativo no catálogo institucional
    Quando envia o pedido com chave de operação válida
    Então recebe um protocolo com retrato do exame, autor e horário do servidor
    E nenhum estudo, arquivo, resultado, laudo ou evento é criado

  Cenário: CA-RIS-02 Menor privilégio e revogação
    Dado um formulário aberto por operador autorizado
    Quando sua concessão PEP é revogada antes do POST
    Então criação, detalhe e lista não revelam pedidos daquele paciente
    E capacidade RIS sem acesso PEP não concede acesso ao paciente
    E capacidade apenas de consulta não autoriza criar

  Cenário: CA-RIS-03 Fechamento antes da confirmação
    Dado um formulário para encontro inicialmente aberto
    Quando o encontro é fechado antes do POST
    Então o envio retorna conflito sem criar pedido
    E retry também é bloqueado pelo fechamento
    Mas o histórico continua consultável dentro do escopo PEP atual

  Cenário: CA-RIS-04 Consultar apenas a página autorizada
    Dado mais de 25 pedidos acessíveis e pedidos de outro paciente fora do escopo
    Quando consulta a primeira página e um detalhe autorizado
    Então somente os 25 pedidos renderizados e o detalhe recebem ACCESS
    E nenhum pedido fora de escopo é mostrado ou auditado como leitura
    E as relações renderizadas não causam consultas por item

  Cenário: CA-RIS-05 Retry concorrente e preservação do retrato
    Dado dois envios simultâneos com mesma chave, ator, encontro e exame
    Quando são processados no PostgreSQL
    Então ambos retornam um único pedido original
    E alteração ou desativação posterior do catálogo não modifica o retrato
    E retry equivalente com encontro aberto preserva autor e horário
    Mas chave com outro conteúdo retorna conflito sem revelar o pedido existente
    E uma chave nova cria solicitação distinta somente com exame ativo

  Cenário: CA-RIS-06 Falha de auditoria e imutabilidade
    Quando a auditoria de criação falha
    Então não há pedido parcial nem confirmação de sucesso
    E pedidos não têm edição ou exclusão nas entradas da aplicação
    E logs e auditlog genérico não incluem nome de paciente ou retrato do exame
    E falha na auditoria de leitura não entrega conteúdo identificável

  Cenário: CA-RIS-07 Sessão, CSRF, mobile e offline
    Quando usa as rotas sem sessão, sem CSRF ou com método inadequado
    Então a operação é impedida e a resposta mantém no-store
    E telefone e tablet não têm overflow nem violações axe sérias ou críticas
    E tentativa offline não confirma nem guarda pedido ou página privada
