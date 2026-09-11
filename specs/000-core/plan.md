# Plano Técnico — Spec 000 Core

## Arquitetura

Preservar o monólito Django e preparar a reorganização incremental do app atual para bounded contexts `apps/core`, `apps/documents` e `apps/audit`. Nenhuma extração para microserviço é permitida.

## Modelo de Dados

Nesta fase, os modelos atuais permanecem fonte de verdade. A reorganização física será feita em etapas com migrations de estado compatíveis e sem renomeações destrutivas no mesmo deploy.

## Rotas e Views

O mapa inicial está em `contracts/routes.md`. Rotas `api/v1/*` são consideradas legado incompatível com o alvo e entram em plano de descontinuação; não devem receber novas funcionalidades.

## Formulários e Validação

Contratos iniciais em `contracts/forms.md`. Validações de permissão e domínio devem ficar no backend, nunca apenas no template.

## Templates e Componentes HTMX

Manter templates atuais durante a estabilização. A migração de Bulma para Tailwind + daisyUI deve ocorrer por componentes e specs aprovadas, não por substituição global imediata.

## Eventos Internos

Chat/notificações continuam via Channels. Jobs futuros usam Celery/Redis. Contrato inicial em `contracts/events.asyncapi.yaml`.

## PWA

O Core deve fornecer base de sessão, logout e limpeza de dados locais necessária pela Spec 014. Não cachear páginas autenticadas com dados sensíveis sem política explícita.

## Segurança e LGPD

- sessão Django e MFA;
- RBAC/ABAC em views/serviços/objetos;
- auditoria de ações sensíveis;
- proteção de dados em repouso e trânsito;
- inventário de dados pessoais e retenção antes dos módulos clínicos.

## Migrações

Nenhuma migration nesta etapa de documentação. Futuras migrations devem possuir estratégia de rollback e teste.

## Testes

- preservar suíte existente;
- adicionar testes de arquitetura para impedir novas rotas `/api/` públicas;
- ampliar testes de autorização por objeto;
- criar aceitação Gherkin para fluxos críticos do Core.

## Rollout

1. Aprovar Spec 000 e ADRs.
2. Inventariar consumidores da API atual.
3. Congelar expansão da API pública.
4. Migrar consumidores para alternativas internas.
5. Reorganizar apps por etapas.
6. Migrar frontend por componentes.
7. Só então remover legado incompatível.