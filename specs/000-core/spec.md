# Spec 000 — Core: autenticação, auditoria, documentos e workspaces

## Contexto

O AegisShare atual é o núcleo documental e de segurança que será preservado como **Core** do HIS. O objetivo desta spec é estabilizar o comportamento existente, eliminar incompatibilidades com a constituição do HIS e preparar a migração para bounded contexts sem quebrar funcionalidades.

## User Stories

- Como usuário interno, quero autenticar com sessão segura e MFA para acessar o sistema conforme meu papel.
- Como colaborador autorizado, quero armazenar, versionar, compartilhar e auditar documentos com segurança.
- Como administrador, quero controlar usuários, workspaces, permissões, sessões e auditoria.
- Como auditor, quero rastrear ações relevantes sem alteração retroativa dos registros.

## Requisitos Funcionais

- **RF-CORE-01** Autenticação por sessão Django com suporte a MFA TOTP.
- **RF-CORE-02** Autorização por papel e por objeto, com menor privilégio.
- **RF-CORE-03** Upload, versionamento, preview e download de documentos conforme política de acesso.
- **RF-CORE-04** Compartilhamento interno e links temporários controlados.
- **RF-CORE-05** Workspaces e solicitações documentais permanecem disponíveis.
- **RF-CORE-06** Chat e notificações continuam internos e autenticados.
- **RF-CORE-07** Toda ação sensível relevante deve gerar trilha de auditoria.
- **RF-CORE-08** Rotas REST públicas `api/v1/*` devem ser descontinuadas antes do HIS entrar em produção, com migração documentada para alternativas internas.
- **RF-CORE-09** O Core deve expor serviços Python internos reutilizáveis pelos módulos clínicos, sem exigir API HTTP pública.

## Requisitos Não Funcionais

- **RNF-CORE-01** Documentos sensíveis cifrados com AES-256-GCM antes do armazenamento externo quando aplicável.
- **RNF-CORE-02** PostgreSQL transacional e Redis para cache/Channels/filas conforme ambiente.
- **RNF-CORE-03** Nenhuma permissão pode existir apenas no template; a view/serviço deve validar o acesso.
- **RNF-CORE-04** Health checks e logs estruturados devem permanecer operacionais.
- **RNF-CORE-05** Mudanças estruturais devem ser compatíveis com rollout incremental e migrations reversíveis.

## Critérios de Aceitação

```gherkin
Cenário: Usuário sem acesso tenta abrir um documento
  Dado um usuário autenticado sem permissão sobre o documento
  Quando acessa a rota de detalhe ou download
  Então o sistema nega o acesso
  E registra o evento de segurança quando aplicável
```

```gherkin
Cenário: Operação interna não depende de API REST pública
  Dado um fluxo do Core utilizado pela interface web
  Quando o usuário executa a ação
  Então a ação é processada por view, formulário, HTMX, WebSocket ou serviço interno
  E nenhuma API REST pública é necessária
```

## Telas e Fluxos

- Dashboard e home.
- Login, MFA, perfil e segurança.
- Arquivos, detalhe, versões, compartilhamento e lixeira.
- Workspaces e solicitações.
- Chat e notificações.
- Auditoria.

## Fora de Escopo

- PEP, ADT, prescrição, enfermagem e demais fluxos clínicos.
- Migração física completa para `apps/core`, `apps/documents` e `apps/audit` nesta etapa de documentação.

## Dependências

- Django, Channels, PostgreSQL, Redis.
- Serviços existentes de criptografia, compartilhamento, arquivos e segurança.

## Riscos

- Remover `api/v1/*` sem inventário de consumidores pode quebrar integrações existentes.
- Troca de Bulma para Tailwind/daisyUI pode gerar regressão visual se feita de uma vez.
- Mudança de licença exige decisão explícita do mantenedor antes de alterar `LICENSE`.

## Rastreabilidade

| Requisito | Rota/View | Template | Teste |
|---|---|---|---|
| RF-CORE-01 | login, login/2fa, segurança | templates de registro/segurança | auth/security tests |
| RF-CORE-03 | arquivos/* | `templates/arquivos/*` | file service/web tests |
| RF-CORE-06 | chat/*, notificações/* | `templates/chat/*`, `templates/notifications/*` | chat/web tests |
| RF-CORE-07 | `/auditoria/` | `templates/audit/list.html` | audit tests |
| RF-CORE-08 | `api/v1/*` (transição) | — | teste que proíbe novas APIs públicas |
