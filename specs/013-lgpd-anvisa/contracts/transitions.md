# Transições e limites — Spec 013 v1 (v1 aprovada)

| Estado atual | Ação | Novo estado | Nota |
|---|---|---|---|
| inexistente | registrar solicitação | RECEIVED | evento inicial sem nota duplicada |
| RECEIVED | iniciar análise | IN_REVIEW | opcional |
| IN_REVIEW | encerrar administrativamente | CLOSED | obrigatória |
| CLOSED | nenhuma | — | sem reabertura v1 |

Um evento descreve uma mudança administrativa, nunca autorização de tratamento. `CLOSED` significa somente que o profissional registrou o encerramento do acompanhamento na UI.

As operações não:

- alteram ou excluem paciente, encontro, evolução ou documento;
- concedem/revogam acesso PEP;
- chamam exportação da Spec 012;
- eliminam recibos, auditoria ou backups;
- enviam mensagens ao titular;
- classificam o pedido como legalmente devido, deferido ou indeferido.

## Concorrência e falha

Ao processar POST, obter a solicitação autorizada, bloquear sua linha, revalidar escopo e comparar `expected_status`. Somente o próximo estado da tabela é aceito. Estado e evento são confirmados juntos com auditoria; falha reverte todos.

Dois operadores partindo de RECEIVED: um cria o evento IN_REVIEW, o outro recebe 409. Retry de POST já confirmado também recebe 409; a interface orienta consultar o histórico. Nota do primeiro evento não é sobrescrita.

Perda de escopo retorna 404 sem revelar a solicitação; perda de capacidade retorna 403. Nenhum retry pode recuperar permissão revogada.
