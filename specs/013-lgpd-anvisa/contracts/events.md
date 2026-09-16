# Histórico e auditoria — Spec 013 v1 (v1 aprovada)

## Eventos persistidos

`DataSubjectRequestEvent` registra criação, início de análise e encerramento segundo `transitions.md`. É histórico administrativo restrito; não há broadcast, push ou consumidor assíncrono na v1.

## Auditlog

- CREATE de solicitação e evento: ator autenticado, UUIDs e metadados de estado/data.
- UPDATE de solicitação: somente mudança administrativa de status.
- ACCESS: solicitações efetivamente renderizadas na página de lista e detalhe/form de transição, associado ao ator.
- `summary` e `note` ficam excluídos de diffs/serialização auditável; `__str__` não inclui dados identificáveis.
- Falhas de banco: mensagem operacional genérica; nunca payload do formulário, nota ou resumo em logs.

Criação/transição e respectivos registros de auditoria são atômicos. Falha de auditoria não permite mensagem de sucesso ou persistência parcial. Nenhum AsyncAPI é introduzido sem um canal real; eventos futuros precisam de extensão aprovada.
