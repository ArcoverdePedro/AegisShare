# AegisShare

**Portal seguro para troca, organização, rastreabilidade e colaboração de documentos entre equipes e clientes.**

AegisShare é uma aplicação Django/ASGI com armazenamento no IPFS via Pinata, criptografia antes do envio, versionamento, auditoria, workspaces por cliente, links temporários, solicitações de documentos, chat em tempo real e API.

> O IPFS é tratado como camada de armazenamento. Novos arquivos são cifrados antes do upload; o CID não é mais usado como mecanismo de autorização.

## Recursos principais

- AES-256-GCM antes do IPFS, com chave aleatória por versão.
- Envelope encryption: `FILE_ENCRYPTION_KEY` protege as chaves de conteúdo.
- SHA-256 do conteúdo e verificação de integridade no download.
- Versionamento de arquivos.
- Permissões por proprietário, workspace e concessões explícitas.
- Links temporários com senha, expiração, limite de downloads e revogação.
- Workspaces, pastas e tags.
- Lixeira com restauração e retenção.
- Solicitações de documentos e acompanhamento de pendências.
- Comentários e chat em tempo real.
- Notificações internas.
- 2FA TOTP com códigos de recuperação.
- Inventário e revogação de sessões.
- API tokens armazenados somente como hash.
- Audit log com `django-auditlog` e tela administrativa em `/auditoria/`.
- Sentry opcional, logging JSON e health checks.
- PostgreSQL e Redis internos ou externos.
- Quatro topologias de Docker Compose.
- CI com PostgreSQL, Redis, testes, lint, migrations e smoke test do Compose.

## Arquitetura

```text
                        HTTPS
                          |
                   Reverse Proxy
                          |
                    +-----v------+
                    | AegisShare |
                    | Django ASGI|
                    |  Granian   |
                    +--+------+--+
                       |      |
                +------v-+  +-v---------+
                | Redis  |  | PostgreSQL|
                +--------+  +-----------+
                       |
     arquivo -> validação -> ClamAV opcional -> AES-256-GCM
                       |
                       v
                   Pinata/IPFS
                (conteúdo cifrado)
```

Redis é usado por Channels e cache. Sem Redis, esses componentes usam memória local e a aplicação força um único worker para manter consistência.

## Requisitos

- Docker e Docker Compose para o deploy recomendado.
- Token JWT da Pinata.
- `SECRET_KEY` e `FILE_ENCRYPTION_KEY` fortes.
- HTTPS/reverse proxy em produção.

## Primeira configuração

Copie o exemplo:

```bash
cp .env-example .env
```

Gere as chaves:

```bash
docker compose run --rm --no-deps aegis_share python manage.py generate_secrets
```

Copie os dois valores exibidos para `.env` e configure pelo menos:

```env
SECRET_KEY=...
FILE_ENCRYPTION_KEY=...
PINATA_JWT_TOKEN=...
POSTGRES_PASSWORD=...
ALLOWED_HOSTS=files.exemplo.com
CSRF_TRUSTED_ORIGINS=https://files.exemplo.com
```

Para produção atrás de HTTPS mantenha:

```env
DEBUG=false
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

Depois:

```bash
docker compose up -d --build
```

No primeiro acesso, se ainda não houver administrador, `/setup/` permite criar o primeiro superusuário.

## Docker Compose

### 1. Django + Redis + PostgreSQL

Padrão recomendado:

```bash
docker compose up -d --build
```

PostgreSQL e Redis ficam somente na rede Docker. Apenas a aplicação publica porta no host.

### 2. Django + Redis + PostgreSQL externo

```bash
docker compose -f compose.no-postgres.yml up -d --build
```

Configure:

```env
EXTERNAL_DATABASE_URL=postgresql://usuario:senha@host:5432/aegisshare
```

### 3. Django + PostgreSQL + Redis externo ou sem Redis

```bash
docker compose -f compose.no-redis.yml up -d --build
```

Para Redis externo:

```env
EXTERNAL_REDIS_URL=redis://host:6379/0
```

Para operar sem Redis:

```env
EXTERNAL_REDIS_URL=
```

Nesse modo o entrypoint reduz `WEB_WORKERS` para `1`.

### 4. Somente Django

Banco externo obrigatório; Redis externo opcional:

```bash
docker compose -f compose.no-postgres-no-redis.yml up -d --build
```

```env
EXTERNAL_DATABASE_URL=postgresql://usuario:senha@host:5432/aegisshare
EXTERNAL_REDIS_URL=redis://host:6379/0
```

`EXTERNAL_REDIS_URL` pode ficar vazio para execução com um único worker.

## Inicialização do container

O entrypoint:

1. aguarda o banco responder;
2. executa `python manage.py migrate --noinput`;
3. executa `python manage.py collectstatic --noinput`;
4. inicia Granian/ASGI.

As opções podem ser controladas por:

```env
RUN_MIGRATIONS=true
COLLECT_STATIC=true
WEB_WORKERS=2
DB_STARTUP_ATTEMPTS=30
```

Em ambientes com várias réplicas, execute migrations em apenas uma delas e use `RUN_MIGRATIONS=false` nas demais.

## Variáveis de ambiente

| Variável | Uso |
|---|---|
| `SECRET_KEY` | segredo criptográfico do Django |
| `FILE_ENCRYPTION_KEY` | chave-mestra que protege as chaves AES dos arquivos |
| `POSTGRES_DB` | banco do PostgreSQL interno |
| `POSTGRES_USER` | usuário do PostgreSQL interno |
| `POSTGRES_PASSWORD` | senha do PostgreSQL interno |
| `EXTERNAL_DATABASE_URL` | banco externo nos composes sem PostgreSQL |
| `EXTERNAL_REDIS_URL` | Redis externo nos composes sem Redis |
| `DATABASE_URL` | conexão direta quando Django roda fora dos composes fornecidos |
| `REDIS_URL` | Redis direto quando Django roda fora dos composes fornecidos |
| `PINATA_JWT_TOKEN` | autenticação da Pinata |
| `PINATA_GATEWAY_URL` | URL de leitura dos CIDs |
| `FILE_MAX_UPLOAD_MB` | limite de upload |
| `FILE_RETENTION_DAYS` | retenção da lixeira |
| `CLAMAV_ENABLED` | ativa varredura ClamAV |
| `CLAMAV_REQUIRED` | bloqueia upload se o ClamAV não responder |
| `SENTRY_DSN` | Sentry opcional |
| `WEB_WORKERS` | workers Granian |

Consulte `.env-example` para a configuração completa.

## Criptografia e arquivos legados

Novos uploads seguem:

```text
arquivo original
   |
   +--> validação de tamanho/MIME
   +--> ClamAV opcional
   +--> SHA-256
   +--> AES-256-GCM
   +--> Pinata/IPFS
```

Cada versão recebe uma chave AES aleatória. A chave de conteúdo é cifrada pela `FILE_ENCRYPTION_KEY` e apenas a chave protegida é armazenada no banco.

A migration de upgrade preserva arquivos anteriores como `FileVersion v1` legada e não criptografada. Para obter a mesma confidencialidade dos novos uploads, envie uma nova versão do arquivo legado.

**Não perca `FILE_ENCRYPTION_KEY`.** Sem ela, versões cifradas não podem ser recuperadas.

## Auditoria

O projeto usa `django-auditlog` para alterações e eventos de acesso. Campos sensíveis, como hashes de tokens, segredo TOTP e chave protegida do arquivo, são excluídos do histórico.

Administradores podem consultar:

```text
/auditoria/
```

A interface permite filtrar por ator, modelo e ação.

## Health checks

```text
/health/live/      processo HTTP vivo
/health/ready/     banco e cache prontos
/health/services/  diagnóstico ampliado, incluindo Pinata
```

`/health/live/` e `/health/ready/` não dependem da Pinata; uma falha do provedor de armazenamento não deve reiniciar o processo web saudável.

## API

A API usa tokens Bearer gerados em **Segurança**:

```http
Authorization: Bearer ags_...
```

Endpoints iniciais:

```text
GET  /api/v1/files/
POST /api/v1/files/
GET  /api/v1/files/<id>/
GET  /api/v1/files/<id>/download/
```

O token completo é exibido somente no momento da criação; o banco armazena apenas SHA-256.

## Desenvolvimento

```bash
uv sync --dev
uv run python manage.py migrate
uv run python manage.py runserver
```

Validações:

```bash
uv run ruff check aegis_share mysite
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test --verbosity 2
```

## Manutenção

Expurgo da lixeira:

```bash
python manage.py purge_trash
```

O Dependabot mantém dependências Python, GitHub Actions e imagens Docker sob atualização automática; os PRs passam pela CI antes de qualquer merge automático.

## Segurança

Leia [SECURITY.md](SECURITY.md) antes de publicar uma instalação na internet.

## Licença

Consulte [LICENSE](LICENSE).
