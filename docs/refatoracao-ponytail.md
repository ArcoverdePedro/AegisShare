# Refatoração Ponytail — 2026-09-16

Nível usado: 1/2/3 — reuso do projeto, Django nativo e funções simples.

## Alterações

- **PEP:** nove FBVs substituem nove CBVs e três mixins. Autorização, formulário, persistência, auditoria e redirect ficam explícitos. Helpers pequenos atendem consultas e paginação realmente reutilizadas. URLs e templates mantidos; métodos declarados GET/HEAD nas consultas e GET/HEAD/POST nos formulários, conforme os contratos GET/POST existentes.
- **Eventos:** `apps.clinical.events.send_after_commit` substitui quatro implementações de transporte. Cada módulo continua validando seu próprio payload e contrato; sem publicação antes do commit ou após rollback.
- **Permissões:** prescrição e enfermagem reutilizam `is_internal_professional`, mantendo a exclusão de clientes e a exigência das capacidades específicas.
- **ADT:** forms usam diretamente `active_admissions_for_user`; removidos dois wrappers sem comportamento. `dict` nativo substitui `OrderedDict` no agrupamento por localização, preservando a ordem.
- **Core:** removidos o módulo de reexports `aegis_share.views` e dois adaptadores de utils sem consumidores encontrados no repositório. Integrações externas que importem esses símbolos devem importar diretamente os controllers em `aegis_share.web`, `files_for_user` ou `grant_access`; rotas HTTP não foram removidas.

Saldo do código de aplicação: **215 linhas a menos**, incluindo o novo helper de eventos e excluindo testes/documentação. Nenhuma dependência ou migration adicionada.

## Validação

- Suíte completa em PostgreSQL 18 descartável: **419 testes, OK, sem pulados**.
- Jornadas Playwright existentes do PEP: **2 passaram**, sem retries; cadastro, encontro, evolução, adendo, negação de acesso, axe e telefone/tablet.
- Regressão de paginação: busca e escopo preservados, última página, números inválidos e HEAD.
- Ruff, Django check, makemigrations --check --dry-run, compileall e git diff --check passaram.
- Verificação visual local com agent-browser: página inicial renderizada, navegação presente e sem erros reportados pelo navegador.
- Uma execução SQLite foi interrompida após deixar de progredir; a evidência completa é a execução posterior bem-sucedida em PostgreSQL. CI remoto e deploy não executados.

## Limites da simplificação

A busca de duplicações e referências abrangeu os diretórios de aplicação, scripts, templates e JavaScript. A refatoração foi aplicada onde havia redução concreta, sem reescrever cada arquivo por uniformidade. CBVs estáveis fora do PEP, validações clínicas, constraints, locks, criptografia, fila offline e scripts de segredos foram preservados. Referências indiretas de signals não foram tratadas como código morto. Não foram criadas classes base, workflows genéricos ou abstrações para usos futuros.
