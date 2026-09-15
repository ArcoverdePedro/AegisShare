# Constituição — AegisShare HIS

## Status
Aprovada como baseline do ciclo SDD inicial.

## Princípios inegociáveis

1. **Segurança e privacidade por padrão** — LGPD, criptografia AES-256-GCM para documentos sensíveis, menor privilégio, auditoria rastreável e proteção de segredos.
2. **Uso interno e sem API REST pública** — interfaces de usuário são server-rendered; integrações externas usam arquivos, mensageria, jobs internos ou WebSockets autenticados.
3. **Fullstack monolítico** — Django, templates server-side, HTMX e Alpine.js no mesmo repositório e deploy.
4. **PWA como camada de apresentação** — instalação em dispositivos móveis, offline parcial e sincronização controlada, sem duplicar codebase.
5. **Interoperabilidade por arquivos e mensageria** — HL7 v2.x, DICOM, TISS e FHIR somente por importação/exportação de arquivos ou fluxos internos.
6. **Rastreabilidade clínica** — toda leitura ou alteração relevante de dado clínico deve ser auditável.
7. **Modularidade dentro do monólito** — bounded contexts claros; o AegisShare documental atual passa a ser o Core.
8. **Testes guiados por spec** — unitários, views/integração, aceitação Gherkin, E2E, segurança, acessibilidade e carga quando aplicável.
9. **Conformidade regulatória** — LGPD e requisitos regulatórios aplicáveis, incluindo avaliação de ANVISA/RDC 657/2022 quando houver enquadramento como SaMD.
10. **Observabilidade desde o início** — logs estruturados, métricas, traces e health checks.
11. **Sem breaking changes silenciosos** — migrações reversíveis, rollout explícito e compatibilidade documentada.
12. **Código aberto** — licenciamento `AGPL-3.0-only` e governança pública documentada.

## Regra de ouro do SDD

Nenhuma implementação de feature clínica, administrativa ou PWA deve ser iniciada sem `spec.md` aprovado, `plan.md`, `tasks.md`, contratos internos e critérios de aceitação rastreáveis.

## Gates mínimos

- lint e formatação;
- `python manage.py check`;
- migrations versionadas e reversíveis;
- testes unitários e de views;
- aceitação Gherkin para requisitos críticos;
- E2E Playwright para jornadas-chave;
- SAST/SCA;
- acessibilidade WCAG 2.1 AA;
- Lighthouse PWA >= 90 quando aplicável;
- validação de segurança/LGPD.

## Conflitos e transições ainda abertas

A evolução para o HIS mantém decisões explícitas e incrementais para os pontos que ainda não atingiram integralmente a arquitetura alvo:

- as rotas legadas `api/v1/*` permanecem somente como compatibilidade temporária; novas APIs REST públicas são proibidas e a retirada depende do inventário/migração operacional definido na Spec 000;
- o frontend ainda usa Bulma/crispy-bulma; a migração para Tailwind + daisyUI segue o plano incremental da Spec 000, sem reescrita em massa;
- gates clínicos, jurídicos e de governança definidos pelas specs permanecem bloqueantes mesmo quando a infraestrutura técnica correspondente já existe.

## Transições concluídas

- estrutura `.specify/`, `specs/` e bounded contexts SDD criada e utilizada como fonte de verdade;
- licença do projeto migrada de MIT para `AGPL-3.0-only`, com texto integral em `LICENSE` e metadado correspondente em `pyproject.toml`.

Esses estados devem continuar sendo atualizados por tarefas e ADRs aprovados, sem remoções ou migrações silenciosas.
