# Eventos e auditoria — Spec 012 v1 (v1 aprovada)

Não há publicação WebSocket/Celery nem consumidor assíncrono na v1; logo não se define canal AsyncAPI fictício.

- **Leitura:** ACCESS do Patient selecionado ao gerar o arquivo, associado ao ator autenticado.
- **Geração:** CREATE auditado de PatientExportReceipt, com UUIDs, timestamp, contract_version e content_sha256.
- **Falha:** mensagem operacional genérica; sem JSON exportado, nome, nascimento, CPF ou dados do formulário no log.

GET não cria recibo. POST inválido/negado não cria recibo de sucesso. Falha em auditoria ou recibo aborta a transação e impede a resposta attachment. Conclusão HTTP não comprova recebimento por outro sistema.

Eventos futuros como `fhir.resource.imported` dependem de extensão aprovada com consumidor, payload minimizado e semântica de entrega explícitos.
