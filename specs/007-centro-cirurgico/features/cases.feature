# language: pt
Funcionalidade: Registrar solicitação de procedimento sem agendar cirurgia
  # Evidências e rastreabilidade executável em ../validation.md.

  Cenário: CA-SURG-01 Solicitação para encontro acessível
    Dado um profissional com consulta e criação e acesso PEP ao encontro aberto
    Quando registra um procedimento ativo com chave válida
    Então recebe protocolo, retrato, autor e horário definidos pelo servidor
    E vê aviso de ausência de agendamento ou autorização cirúrgica
    E não há cirurgia realizada, agenda, reserva de material ou evento

  Cenário: CA-SURG-02 Menor privilégio e revogação
    Dado um formulário aberto por profissional com concessão PEP
    Quando a concessão é revogada antes do POST
    Então envio, lista e detalhe não revelam solicitações daquele paciente
    E capacidade de consulta não permite criar
    E capacidade do módulo não concede acesso PEP nem reativa paciente inativo

  Cenário: CA-SURG-03 Encontro fechado
    Quando o encontro é fechado antes do envio ou retry equivalente
    Então a operação retorna conflito sem solicitação nova
    Mas o histórico permanece consultável dentro do escopo PEP atual

  Cenário: CA-SURG-04 Consulta paginada sem N mais um
    Dado mais de 25 solicitações acessíveis e solicitações fora do escopo
    Quando consulta a primeira página e um detalhe autorizado
    Então audita somente os 25 itens renderizados e o detalhe
    E não mostra solicitações fora de escopo nem faz consultas relacionadas por item

  Cenário: CA-SURG-05 Concorrência, retrato e chave incompatível
    Quando dois envios equivalentes com mesma chave chegam simultaneamente no PostgreSQL
    Então retornam uma única solicitação original
    E retrato, autor e horário persistem após alteração ou desativação do catálogo
    E retry autorizado em encontro aberto retorna original mesmo com procedimento inativo
    Mas nova chave com procedimento inativo é bloqueada
    E chave incompatível entre atores, procedimentos ou encontros retorna conflito sem revelar registro
    E uma nova chave válida representa nova solicitação

  Cenário: CA-SURG-06 Auditoria e preservação
    Quando a auditoria de criação falha
    Então a solicitação é revertida sem confirmação parcial
    E falha de auditoria de leitura não entrega conteúdo identificável
    E não há edição ou exclusão de solicitação nas entradas da aplicação
    E logs e auditlog genérico não copiam nome de paciente ou retrato do procedimento

  Cenário: CA-SURG-07 Sessão, CSRF, telefone e offline
    Quando usa as rotas sem sessão, sem CSRF ou com método inadequado
    Então a operação é impedida com privacidade mantida na resposta
    E telefone e tablet não têm overflow ou violações axe sérias ou críticas
    E tentativa offline não confirma nem persiste solicitação ou página privada
