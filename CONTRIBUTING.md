# Contribuindo com o AegisShare

## Objetivo de arquitetura

O projeto privilegia manutenção simples. Evite criar novas camadas sem necessidade.

- `aegis_share/models.py`: estado e invariantes simples do domínio.
- `aegis_share/services/`: regras reutilizáveis, segurança e integrações externas.
- `aegis_share/web/`: controllers HTTP/HTML/API.
- `aegis_share/tests/`: testes organizados por responsabilidade.
- `templates/`: apresentação; não deve conter regra de autorização.
- `mysite/settings.py`: configuração somente por ambiente.

Uma mesma regra de negócio não deve ser duplicada em formulário, view e API. Coloque-a em `services/` ou em um módulo de política, e faça as interfaces chamarem a mesma implementação.

## Ambiente local

Requer Python 3.14 e `uv`.

```bash
uv sync --dev
uv run python manage.py migrate
uv run python manage.py runserver
```

Sem `DATABASE_URL`, o modo `DEBUG=true` usa SQLite. Sem Redis, Channels/cache usam memória local.

## Antes de abrir um PR

Execute:

```bash
uv run ruff check aegis_share mysite
uv run ruff format --check aegis_share mysite
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test --verbosity 2
```

Para validar a imagem real:

```bash
cp .env-example .env
# configure valores de teste válidos
docker compose up -d --build
curl http://127.0.0.1:8000/health/ready/
docker compose down -v
```

## Regras para arquivos e segurança

- Nunca envie conteúdo em claro ao IPFS para funcionalidades privadas novas.
- Nunca armazene token público/API em texto puro.
- Nunca registre `FILE_ENCRYPTION_KEY`, `wrapped_key`, segredo TOTP, senha ou código de recuperação em logs/audit log.
- Toda rota de arquivo deve usar os selectors/permissões centralizados.
- Toda operação de upload deve passar por `file_policy.validate_uploaded_file` e pelo serviço de arquivos.
- Integrações externas precisam de timeout e erro tipado.
- WebSocket deve validar participação/autorização antes de entrar no grupo.

## Models e migrations

Mudanças em models exigem migration versionada.

```bash
uv run python manage.py makemigrations
uv run python manage.py makemigrations --check --dry-run
```

Não edite migrations que já foram publicadas em `master`; crie uma nova migration.

Para alterações que transformam dados existentes, prefira uma data migration separada e reversível quando possível.

## Testes

Um bug de autorização deve ganhar um teste de regressão.

Novas funcionalidades críticas devem testar pelo menos:

1. caminho permitido;
2. caminho negado;
3. dados inválidos;
4. comportamento de segurança/privacidade relevante.

Integrações como Pinata devem ser mockadas nos testes unitários. O smoke test Docker cobre a inicialização da stack real.

## Commits

Prefira mensagens curtas por intenção:

```text
feat: adiciona ...
fix: corrige ...
security: protege ...
refactor: centraliza ...
ops: prepara ...
test: cobre ...
docs: documenta ...
```

## Pull Requests

PRs devem permanecer em draft enquanto houver alteração estrutural incompleta. Não contorne uma CI vermelha com merge manual; corrija a causa ou documente explicitamente uma limitação inevitável.
