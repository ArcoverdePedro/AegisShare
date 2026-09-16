# Evidências — Spec 013 v1

Data: 2026-09-16. Aprovação explícita do mantenedor: “aprovado, continue”.

## Escopo entregue

Cadastro, lista paginada, detalhe e transições administrativas em FBVs. Autorização por capacidade e escopo PEP, histórico com ator/horário, auditoria minimizada, transações com bloqueio de linha e conflito HTTP 409. Migration inicial reversível e integração ao menu. O middleware compartilhado `PrivateWorkflowMiddleware` protege este módulo e a exportação da Spec 012.

## Validação local

| Gate | Resultado |
|---|---|
| Ruff em aegis_share/apps/mysite e preparação E2E | Passou |
| Ruff format do novo app | Passou |
| Django check; makemigrations --check --dry-run | Sem problemas; sem migrations pendentes |
| Suíte Django completa em PostgreSQL 18 descartável | **418 testes passaram, sem testes pulados** |
| Novo módulo | 21 testes, incluindo concorrência real entre dois POSTs no PostgreSQL |
| Compliance + interoperabilidade em SQLite | 38 testes passaram antes da adição do teste específico de concorrência |
| Migration SQLite descartável | Aplicar → reverter → reaplicar: passou |
| Playwright 1.63.0 + Chromium correspondente | **5 jornadas passaram**, sem retries |
| Axe / responsividade | Lista, cadastro, detalhe e transição em 390×844 e 768×1024: sem violações sérias/críticas e sem overflow da página |
| Privacidade PWA | Offline sem confirmação de mutação, sem payload da solicitação em cache/armazenamento/fila |
| Bandit no novo app, excluindo testes | Sem achados |
| pip-audit no ambiente instalado | Nenhuma vulnerabilidade conhecida encontrada |
| Lighthouse CI na página inicial local | Gates obrigatórios passaram; acessibilidade 98, boas práticas 100, SEO 90, desempenho 73 (aviso) |
| git diff --check | Passou |

As jornadas cobrem o ciclo completo, texto escapado, nota obrigatória no encerramento, negação por escopo, formulário desatualizado, privacidade offline e acessibilidade. A correção de layout substitui texto oculto com posicionamento absoluto por `aria-label` no link, mantendo a tabela em seu contêiner rolável.

## Reproduzir

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test
uv run python tests/e2e/prepare_compliance_journeys.py
npx playwright test --config=playwright.config.cjs tests/e2e/compliance_journeys.spec.js
```

Configure banco descartável PostgreSQL para concorrência e o servidor/base URL conforme `playwright.config.cjs`. A fixture cria dados sintéticos e credenciais públicas de teste; não a execute em produção. A preparação foi adicionada ao workflow Django existente.

## Limites

Evidências locais: o workflow remoto não foi executado nesta entrega. Não foram executados Trivy nem uma stack Compose completa com Redis. Lighthouse foi executado na página inicial, não nas telas autenticadas; não se declara categoria numérica PWA. SQLite não comprova bloqueio de linha.

Nenhum deploy, alteração de banco de produção ou atribuição automática de permissões foi realizado. A implementação registra acompanhamento administrativo e não constitui certificação LGPD/ANVISA, decisão jurídica ou execução de exclusão, anonimização ou exportação. Modelos append-only na aplicação não impedem alterações diretas por administradores do banco.

Guia de ativação e rollback: [solicitacoes-titular.md](../../docs/solicitacoes-titular.md). Rastreabilidade: [spec.md](spec.md).
