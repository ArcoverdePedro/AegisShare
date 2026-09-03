# Changelog

Todas as mudanças relevantes do AegisShare serão registradas neste arquivo.

## [0.2.0] - Em desenvolvimento

### Adicionado

- Criptografia AES-256-GCM antes do armazenamento no IPFS.
- Chave independente por versão e envelope encryption.
- SHA-256 e validação de integridade.
- Versionamento de documentos.
- `django-auditlog` e painel administrativo de auditoria.
- Workspaces, membros e pastas.
- Tags e busca ampliada.
- Links temporários com senha, expiração, limite de downloads e revogação.
- Comentários associados a arquivos.
- Solicitações de documentos e acompanhamento de pendências.
- Notificações internas.
- 2FA TOTP e códigos de recuperação.
- Inventário e revogação de sessões.
- Tokens de API armazenados como hash.
- API inicial em `/api/v1/`.
- Lixeira, restauração e política de retenção.
- ClamAV opcional.
- Sentry opcional e logs JSON.
- Endpoints de liveness/readiness/serviços.
- PostgreSQL configurável por `DATABASE_URL`.
- Redis configurável por `REDIS_URL`.
- Quatro topologias de Docker Compose.
- Testes de segurança, criptografia, permissões, compartilhamento, API e WebSocket.
- Smoke test da stack Docker na CI.

### Alterado

- Python de produção padronizado em 3.14.
- Views divididas em controllers sob `aegis_share/web/`.
- Regras de negócio e integrações movidas para `aegis_share/services/`.
- Política de upload centralizada.
- Acesso a arquivos novos deixa de apontar diretamente para gateways IPFS.
- Dockerfile convertido para build multi-stage.
- Redis e PostgreSQL internos deixam de publicar portas no host.
- Configuração de produção passa a falhar cedo quando segredos obrigatórios estão ausentes/inválidos.

### Segurança

- Corrigida autorização de WebSocket para impedir acesso a conversas de terceiros.
- Corrigida autorização de compartilhamento de arquivos.
- Tokens públicos/API não são persistidos em texto puro.
- Segredo TOTP é criptografado.
- Campos sensíveis são excluídos/mascarados no audit log.
- Uploads passam por validação de tamanho/MIME e podem passar por ClamAV.

### Compatibilidade

- Arquivos existentes são preservados como `FileVersion v1` legada e não criptografada.
- `aegis_share.views` permanece temporariamente como camada de compatibilidade para imports antigos.
