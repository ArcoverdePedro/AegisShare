# Evidências — Spec 012 v1

Data: 2026-09-16. Aprovação: instrução do mantenedor “aprovado, continue”.

## Escopo entregue

- FBV `patient_export`, formulário nativo e template em `/interop/exportar/`.
- Sessão, profissional interno, capacidade dedicada, CSRF e queryset PEP revalidado.
- Arquivo Patient R4 JSON com allowlist de cinco campos e filename técnico.
- Migration `interoperability.0001_initial`: recibo append-only com FKs PROTECT.
- CREATE auditado e ACCESS transacionais; falhas de banco impedem o attachment.
- Middleware de privacidade para incluir respostas de negação/CSRF/erro na política no-store.
- Reuso integral do service worker network-only; nenhuma nova operação IndexedDB, API REST, evento WebSocket, job ou dependência de aplicação.
- Atualização de patch transitiva `click 8.3.0 → 8.3.3` no lockfile para corrigir `PYSEC-2026-2132`, identificada durante o gate SCA.

## Validação local

| Gate | Resultado |
|---|---|
| Ruff: `aegis_share apps mysite` e fixture E2E nova | Passou |
| Ruff format: novo app/settings/urls | Passou |
| Django check e makemigrations --check --dry-run | Passaram; sem alterações de schema pendentes |
| Suíte Django completa | 397 testes, OK, 30 pulados no ambiente SQLite |
| Novo módulo | 18 testes de exportação, autorização, revogação, CSRF, auditoria e imutabilidade |
| Migration em banco SQLite descartável | Aplicar → reverter → reaplicar: passou |
| Playwright 1.63.0 / Chromium correspondente | 4 jornadas passaram: download, negação/validação, offline/cache e mobile/axe |
| Acessibilidade | Sem violações sérias/críticas nos testes axe; telefone 390×844 e tablet 768×1024 sem overflow |
| Bandit no novo app, excluindo testes | Sem achados |
| pip-audit no ambiente sincronizado ao lockfile corrigido | Nenhuma vulnerabilidade conhecida encontrada |
| Granian CLI após atualização de click | `granian --help` passou |
| Lighthouse CI na página inicial local | Gates obrigatórios passaram: acessibilidade 98, boas práticas 100; SEO 90; desempenho 73 (aviso) |
| Compilação Python, sintaxe JS e git diff --check | Passaram |

O Lighthouse existente avalia categorias web atuais, não uma categoria numérica PWA. Portanto não se declara “PWA score ≥ 90”. As invariantes offline/no-cache são verificadas pelo Playwright.

As primeiras execuções locais detectaram uma `.venv` incompleta (`pywebpush` ausente) e incompatibilidade de versões do navegador. O ambiente Python foi sincronizado com `uv sync --frozen --dev`; os resultados finais de navegador usam Playwright 1.63.0 e Chromium revision 1243, correspondentes entre si.

## Rastreabilidade e execução

`features/patient-export.feature` descreve CA-INT-01–06. `spec.md` vincula os cenários aos testes reais: transações/falhas e revogação entre GET/POST usam testes Django; download e política offline têm jornadas Playwright. Não foi instalado outro runner BDD.

A CI existente já descobre o app pelo runner Django e o arquivo `interop_journeys.spec.js` pelo Playwright. Foi acrescentada a preparação `prepare_interop_journeys.py` à etapa de fixtures da CI. Dados e credenciais da preparação são exclusivamente sintéticos.

## Limitações e gates ainda pendentes

- CI remota, Docker Compose, PostgreSQL e Redis não executados nesta entrega local; os 30 testes pulados não contam como aprovados. Testes de concorrência/locks exigem o ambiente PostgreSQL da CI.
- Trivy, mypy/black e validação regulatória externa não executados. Não existe certificação LGPD/ANVISA implícita nos testes técnicos.
- SAST executado no novo módulo; não é auditoria exaustiva de segurança do repositório.
- Uso real exige definição institucional de destinatário, base legal e guarda dos arquivos. O piloto testado usa banco descartável e dados sintéticos.
- Aviso de desempenho Lighthouse na página inicial permanece; este recorte não modifica a página inicial para atingir uma meta de desempenho.
- Ingestão HL7/ASTM, Spec 005 LIS e Spec 013 permanecem próximos incrementos sujeitos a suas próprias specs e aprovações.

Guia operacional: [docs/interoperabilidade.md](../../docs/interoperabilidade.md).
