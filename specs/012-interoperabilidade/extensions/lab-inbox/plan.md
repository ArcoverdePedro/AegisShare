# Plano — recebimento em quarentena

Status: implementado em 2026-09-18; [evidências](validation.md). Nível 1/2/3 — reuso, Django nativo e FBVs.

## Implementação

1. Adicionar os dois modelos ao app interoperability, permissões, Admin de origens e migration reversível. Reusar usuário e auditlog; receipt sem Admin de edição.
2. Form de upload com escopo por origem; handler/middleware específico antes do CSRF impõe limite sem arquivos temporários plaintext. O limite de aceitação documental permanece; o piso do spool em memória passa a cobrir o corpo permitido da caixa. Limite específico ASGI atua antes do spool.
3. Função Python específica de recebimento para limite de bytes, criptografia do Core, autorização revalidada, transação e deduplicação. Extração justificada por testes diretos de concorrência/criptografia e para manter FBV legível; sem framework de adaptadores.
4. Três FBVs e templates com apenas metadados. Excluir blobs das consultas de lista/detalhe; paginação antes da auditoria. Layout existente, sem JS novo.
5. Estender middleware de privacidade para a caixa e respostas antecipadas do handler; manter `/interop/` network-only no service worker existente. Sem evento ou fila offline.
6. Testar vazio/excesso, streaming sem tamanho confiável, tentativa multipart com múltiplos arquivos, ausência de temporários, autenticação/CSRF, revogação, reenvio e concorrência no PostgreSQL. Verificar ciphertext e AAD com helpers existentes somente nos testes, sem criar endpoint de decriptação.
7. Aplicar/reverter/reaplicar migration em banco descartável. Testar falhas criptográficas/auditlog, conteúdo ausente de logs/HTML/cache, paginação sem blobs e sem N+1.
8. Playwright/axe em telefone/tablet, upload/duplicata/negação/offline; gates Ruff, Django, migrations, suíte PostgreSQL, Bandit/pip-audit, Lighthouse. Não afirmar certificação de conteúdo/formato ou execução de CI remoto sem evidência.

## Rollout e retirada

Piloto sintético, origens/capacidades atribuídas explicitamente. Antes de dados reais, definir origem/operadores autorizados, gestão de chaves/backups, retenção e limite agregado. Retirada revoga capacidades e desativa origens; rollback de código preserva ciphertext/recibos. Reverter migration após uso real apagaria evidência e não é o procedimento operacional.
