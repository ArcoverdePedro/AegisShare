# language: pt
Funcionalidade: Acompanhamento interno de solicitações do titular
  # Cobertura Django/Playwright vinculada em ../spec.md; concorrência real validada no PostgreSQL.

  Cenário: CA-LGP-01 Registrar solicitação recebida
    Dado um profissional autorizado com acesso a um paciente ativo no PEP
    Quando envia paciente, categoria e resumo válidos com CSRF
    Então recebe um protocolo de solicitação em estado RECEIVED
    E existe um evento inicial com ator e horário do servidor
    E nenhum dado assistencial do paciente é alterado

  Cenário: CA-LGP-02 Analisar e encerrar administrativamente
    Dado uma solicitação recebida dentro do escopo do profissional
    Quando inicia análise e depois informa uma nota para encerrar
    Então o histórico preserva RECEIVED, IN_REVIEW e CLOSED em ordem
    E a interface mostra Encerrada administrativamente
    E nenhum arquivo é exportado nem dado do paciente é excluído

  Cenário: CA-LGP-03 Revalidar autorização no POST
    Dado um profissional que abriu uma solicitação autorizada
    Quando perde capacidade ou acesso ao paciente antes da submissão
    Então a transição é negada sem revelar conteúdo fora do escopo
    E o status e o histórico permanecem iguais

  Cenário: CA-LGP-04 Impedir transições inválidas ou concorrentes
    Dado dois operadores com formulários baseados no mesmo estado
    Quando enviam a mesma transição concorrentemente
    Então apenas uma transição é persistida
    E o outro operador recebe conflito 409
    E encerrar sem nota, pular análise ou reabrir não é permitido

  Cenário: CA-LGP-05 Reverter falha de auditoria
    Dado uma operação de criação ou transição válida
    Quando a persistência da auditoria falha
    Então a operação e o evento são revertidos
    E a resposta não informa sucesso nem expõe traceback ou conteúdo do pedido

  Cenário: CA-LGP-06 Operar exclusivamente online
    Dado um profissional que acessou a área de solicitações em um dispositivo PWA
    Quando fica sem conexão
    Então novas operações não são confirmadas nem entram em fila offline
    E a navegação exibe apenas o fallback genérico
    E nenhum resumo ou nota está no Cache Storage ou IndexedDB

  Cenário: CA-LGP-07 Minimizar e proteger texto livre
    Dado uma solicitação com resumo e nota sintéticos contendo marcação HTML
    Quando um profissional autorizado consulta o detalhe
    Então o texto é escapado sem executar scripts
    E a leitura é auditada sem copiar resumo e nota ao auditlog
    E a lista não inclui solicitações de pacientes fora do escopo
