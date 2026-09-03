# Segurança do AegisShare

## Modelo de proteção

O AegisShare trata o IPFS como armazenamento não confiável para confidencialidade. Novos arquivos são criptografados antes do upload.

### Criptografia

- AES-256-GCM por versão.
- Chave de conteúdo aleatória por versão.
- `FILE_ENCRYPTION_KEY` protege as chaves de conteúdo.
- SHA-256 verifica integridade do conteúdo original.
- Segredos TOTP também são cifrados com a chave-mestra.
- Tokens públicos e tokens de API são armazenados somente como hash.

Nunca faça commit de:

- `.env`;
- `SECRET_KEY`;
- `FILE_ENCRYPTION_KEY`;
- `PINATA_JWT_TOKEN`;
- tokens de API;
- códigos de recuperação 2FA.

## Relato de vulnerabilidade

Não abra issue pública contendo credenciais, CIDs sensíveis, dados pessoais ou passos de exploração contra uma instalação real.

Em uma instalação própria, rotacione imediatamente qualquer segredo potencialmente exposto e preserve logs necessários à investigação.

## Checklist de produção

- `DEBUG=false`.
- HTTPS ativo no reverse proxy.
- `ALLOWED_HOSTS` explícito.
- `CSRF_TRUSTED_ORIGINS` explícito.
- cookies Secure ativos.
- HSTS somente após confirmar HTTPS em todos os subdomínios aplicáveis.
- PostgreSQL sem porta pública desnecessária.
- Redis sem porta pública desnecessária.
- `FILE_ENCRYPTION_KEY` armazenada em secret manager ou arquivo protegido.
- backup do PostgreSQL testado e restaurável.
- Sentry/monitoramento configurado quando necessário.
- ClamAV ativado quando exigido pela política da organização.
- Dependabot e CI habilitados.
- nenhuma alteração relevante mesclada com CI vermelha.

## Rotação de segredos

### `SECRET_KEY`

Pode ser rotacionada, mas sessões e dados assinados pelo Django podem deixar de ser válidos.

### `PINATA_JWT_TOKEN`

Crie um token novo, atualize o ambiente e revogue o anterior.

### `FILE_ENCRYPTION_KEY`

Essa chave protege as chaves das versões criptografadas. Não substitua o valor diretamente em uma instalação que já possua arquivos cifrados.

Uma rotação correta exige reempacotar as chaves de conteúdo existentes de forma transacional. Até existir um comando específico de rotação, trate `FILE_ENCRYPTION_KEY` como chave persistente de longo prazo, com backup seguro e acesso restrito.

## Arquivos legados

A migration de upgrade preserva CIDs anteriores como versões legadas não criptografadas. Para obter confidencialidade equivalente à arquitetura nova, envie uma nova versão desses arquivos.

## Redis e escala

Sem Redis, Channels e cache usam memória local. O entrypoint reduz a aplicação para um único worker nesse modo. Para múltiplas réplicas ou workers, configure Redis.

## Auditoria

O `django-auditlog` registra alterações e acessos. Campos de segredo são explicitamente excluídos ou mascarados. Revise `/auditoria/` periodicamente em instalações sensíveis.
