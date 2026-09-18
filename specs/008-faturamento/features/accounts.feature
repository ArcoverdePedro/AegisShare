# language: pt
Funcionalidade: Preparar conta sem emitir cobrança
  # Critérios cobertos pelos testes HTTP/concorrência/E2E mapeados em validation.md.

  Cenário: CA-BILL-01 Abrir conta acessível
    Dado capacidades de consulta e abertura e acesso PEP ao encontro
    Quando confirma abertura com chave válida
    Então recebe conta única em preparação com autor e horário do servidor
    E não há guia, pagamento, cobrança ou evento automático
    E encerramento clínico não impede preparação nem é modificado

  Cenário: CA-BILL-02 Revogação e capacidades
    Dado formulários de conta e item abertos por operador autorizado
    Quando a concessão PEP é revogada antes do POST
    Então abertura, lançamento, lista e detalhe ocultam dados daquele paciente
    E consulta não permite mutação nem capacidade financeira concede escopo PEP

  Cenário: CA-BILL-03 Cálculo exato e entrada inválida
    Quando registra quantidade 3 a 0.10 BRL e quantidade 1 a 0.20 BRL
    Então o total exato é 0.50 BRL
    E conta vazia totaliza zero e preço zero é permitido
    Mas quantidade fracionária, zero, negativa ou excessiva é rejeitada
    E preço negativo, não finito, excessivo ou com casas excessivas é rejeitado
    E valores máximos permitidos são multiplicados sem perda de precisão

  Cenário: CA-BILL-04 Retries e concorrência
    Quando operações equivalentes chegam simultaneamente no PostgreSQL
    Então conta e item retornam originais sem duplicação preservando autoria
    E outra chave de abertura para encontro ocupado retorna conflito
    E colisão de chave entre atores, conteúdos ou agregados não revela original
    E novo UUID de item cria lançamento distinto mesmo com conteúdo idêntico

  Cenário: CA-BILL-05 Paginação e total completo
    Dado mais de 25 itens e contas fora de escopo
    Quando consulta detalhe e lista autorizados
    Então renderiza e audita somente registros da página e a conta detalhada
    E total considera todos os itens por agregação exata
    E não carrega coleção completa nem faz queries por item ou revela outro escopo

  Cenário: CA-BILL-06 Auditoria e preservação
    Quando a auditoria de criação falha
    Então a mutação é revertida sem confirmação parcial
    E falha de auditoria de leitura impede entrega identificável
    E não há edição ou exclusão nas entradas da aplicação
    E logs e auditlog genérico não copiam descrição, valores ou nome de paciente

  Cenário: CA-BILL-07 Sessão, CSRF, mobile e offline
    Quando usa rotas sem sessão, sem CSRF ou com método inadequado
    Então a operação é impedida mantendo privacidade da resposta
    E telefone e tablet não têm overflow ou violações axe sérias ou críticas
    E offline não confirma nem persiste conta, item ou página privada
