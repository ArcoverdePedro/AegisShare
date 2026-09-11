# Constituição — AegisShare HIS

## Status
Proposta para aprovação no ciclo SDD inicial.

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
12. **Código aberto** — alvo de licenciamento AGPL-3.0 e governança pública documentada.

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

## Conflitos detectados no repositório atual

A evolução para o HIS requer decisões explícitas antes de código porque o repositório atual possui elementos incompatíveis com esta constituição:

- existem rotas `api/v1/*`, enquanto o alvo proíbe API REST pública;
- a licença atual é MIT, enquanto o alvo definido é AGPL-3.0;
- o frontend atual usa Bulma/crispy-bulma, enquanto a arquitetura alvo define Tailwind + daisyUI;
- ainda não existe a estrutura `.specify/`, `specs/` e bounded contexts alvo.

Esses pontos devem ser tratados por tarefas e ADRs aprovados, sem remoções ou migrações silenciosas.