# language: pt
Funcionalidade: Receber arquivos laboratoriais sem publicar conteúdo clínico
  # Rastreabilidade executável e evidências em ../validation.md.

  Cenário: CA-INBOX-01 Receber arquivo em origem autorizada
    Dado um profissional com capacidades e associação a uma origem ativa
    Quando confirma o upload de um arquivo dentro do limite
    Então recebe um recibo de quarentena com origem declarada, operador e horário
    E nenhum resultado, paciente, pedido ou amostra é criado ou alterado

  Cenário: CA-INBOX-02 Revogar acesso e desativar origem
    Dado um formulário aberto por operador autorizado
    Quando sua associação é revogada antes do POST
    Então não consegue receber nem consultar recibos daquela origem
    E uma origem desativada impede uploads e reenvios mesmo com associação vigente
    Mas seus recibos históricos continuam consultáveis por operadores ainda autorizados

  Cenário: CA-INBOX-03 Validar tamanho sem confiar no cliente
    Quando envia arquivo vazio, incompleto, acima de um MiB ou múltiplos arquivos
    Então o upload é rejeitado sem recibo nem temporário plaintext
    E uma declaração de tamanho menor não permite ultrapassar o limite

  Cenário: CA-INBOX-04 Preservar bytes cifrados
    Dado um arquivo sintético aceito
    Então os bytes originais não aparecem na persistência textual nem na interface
    E decriptar no teste com o AAD correto recupera exatamente os bytes recebidos
    E AAD errado ou ciphertext alterado falha sem produzir plaintext
    E configuração criptográfica inválida impede gravar recibo

  Cenário: CA-INBOX-05 Reenvio concorrente
    Dado dois uploads idênticos para a mesma origem por operadores autorizados
    Quando são processados simultaneamente
    Então existe um único recibo e ambos recuperam esse recibo
    E autoria e horário originais não são sobrescritos
    Mas os mesmos bytes em outra origem autorizada geram recibo distinto

  Cenário: CA-INBOX-06 Auditar sem copiar payload
    Quando recebe, consulta ou reenvia um arquivo
    Então a ação e seu ator são auditados sem payload, chave, filename ou hashes
    E falha de auditoria reverte a criação
    E somente recibos renderizados são auditados em cada página sem carregar blobs

  Cenário: CA-INBOX-07 Fronteira online e acessibilidade
    Dado operador em telefone ou tablet
    Quando acessa a caixa
    Então os controles possuem labels e não há overflow ou violações axe graves
    E respostas inclusive erro e CSRF são no-store
    E perda de conexão não confirma recebimento nem cria fila offline ou cache clínico
