# Tasks — Spec 000 Core

> Spec aprovada em 2026-09-11. Implementação liberada de forma incremental e sem breaking changes silenciosos.

- [x] **T-CORE-01** Inventariar consumidores das rotas `api/v1/*`. Vinculado a RF-CORE-08. A superfície e os consumidores versionados estão documentados em `contracts/api-deprecation.md`; consumidores externos permanecem como gate operacional antes de qualquer remoção.
- [x] **T-CORE-02** Registrar ADR para ausência de API REST pública. Vinculado a RF-CORE-08.
- [x] **T-CORE-03** Definir estratégia de migração dos consumidores da API para views, formulários, arquivos ou jobs internos. Vinculado a RF-CORE-08/09. O plano incremental e reversível está em `contracts/api-deprecation.md`.
- [x] **T-CORE-04** Criar teste de arquitetura que falhe se novas rotas públicas `/api/` forem adicionadas. Vinculado a RF-CORE-08.
- [x] **T-CORE-05** Mapear modelos atuais para `core/documents/audit` sem mover tabelas ainda. Vinculado a RNF-CORE-05. O ownership lógico, dependências e exceções clínicas estão documentados em `contracts/model-boundaries-and-migration.md`.
- [x] **T-CORE-06** Criar plano de migração incremental dos apps com rollback. Vinculado a RNF-CORE-05. O plano preserva tabelas físicas, histórico de migrations/content types e define rollback/gates por lote em `contracts/model-boundaries-and-migration.md`.
- [x] **T-CORE-07** Revisar autorização por objeto nas views de arquivos, workspaces e chat. Vinculado a RF-CORE-02. Uploads agora validam escopo de cliente/workspace/pasta, `can_upload` e links; lixeira e chat deixam de expor objetos após perda de acesso; testes de regressão cobrem os limites revisados.
- [x] **T-CORE-08** Formalizar eventos internos do Core em AsyncAPI. Vinculado a RF-CORE-06/07.
- [x] **T-CORE-09** Definir inventário LGPD e política de retenção inicial. Vinculado a RNF-CORE-01/03. O baseline técnico, inventário, retenção da lixeira, gaps e gates para expurgos estão documentados em `contracts/privacy-retention.md`; prazos jurídicos, direitos do titular e retenção clínica permanecem para a Spec 013.
- [x] **T-CORE-10** Executar mudança de licença MIT -> AGPL-3.0. A aprovação do mantenedor foi materializada pela instrução de fechamento integral do SDD em 2026-09-15; `LICENSE` passa a usar GNU Affero General Public License v3 only (`AGPL-3.0-only`) e `NOTICE` preserva o copyright do projeto.
- [x] **T-CORE-11** Planejar migração visual Bulma -> Tailwind/daisyUI por componente, com testes de regressão. O plano por lotes, coexistência, rollback e gates está em `contracts/frontend-migration.md`.
- [x] **T-CORE-12** Criar testes Gherkin/E2E das jornadas de login, arquivos e compartilhamento. Os cenários estão em `features/core-user-journeys.feature` e são executados no CI por Playwright, incluindo login inválido/válido, abertura de arquivo, concessão de acesso e link público protegido por senha.
