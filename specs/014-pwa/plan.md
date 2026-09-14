# Plano Técnico — Spec 014 PWA

## Arquitetura

`apps/pwa` pertence ao mesmo monólito Django. Manifest, service worker, fallback offline, IndexedDB helpers, Web Push e futura sincronização usam o mesmo deploy e não criam API REST pública.

## Dependências efetivamente adotadas

A implementação inicial validou que wrappers extras não eram necessários para manifest, service worker ou IndexedDB. A solução atual usa:

- APIs nativas do navegador para Service Worker, Cache Storage, IndexedDB e Web Crypto;
- `pywebpush>=2.5,<3` para publicação Web Push/VAPID no backend;
- Django views autenticadas por sessão + CSRF para registrar/revogar subscriptions.

`django-pwa`, `django-webpush`, Workbox e `idb` não foram adicionados porque a fundação atual já atende os contratos com menor superfície de dependências. A decisão de Web Push está registrada no ADR-0007.

## Rotas e Views

- `/offline/` para fallback;
- manifest e service worker servidos pelo app PWA;
- `/pwa/push/config/`, `/pwa/push/subscribe/` e `/pwa/push/unsubscribe/` são rotas internas autenticadas, não API pública;
- sincronização futura reutiliza views/formulários internos existentes sempre que tecnicamente seguro.

## Estratégia de Cache

Definida em `contracts/service-worker.md`. Por padrão, dados clínicos e páginas administrativas são `network-only` até que uma spec declare explicitamente uma exceção segura.

## IndexedDB e Sincronização

Definidos em `contracts/offline-sync.md`. Payloads offline permitidos são cifrados com AES-GCM antes da persistência, associados a `idempotency_key` e não são sincronizados automaticamente enquanto não houver fluxo clínico piloto aprovado.

## Push Notifications

Definidas em `contracts/webpush.md`. O backend publica sem payload de aplicação (`data=None`). Título, corpo e destino são genéricos e fixos no service worker. O clique abre `/notificacoes/`, onde autenticação e autorização são revalidadas.

## Tema e Acessibilidade

O sistema respeita `prefers-color-scheme`, mantém tokens de cor coerentes e cumpre WCAG 2.1 AA. Componentes offline/standalone usam os mesmos tokens de tema.

## Segurança e LGPD

- HTTPS obrigatório;
- service worker limitado ao escopo do app;
- limpeza de dados locais no logout;
- evitar cache de PHI;
- payload offline cifrado e chave local não extraível;
- Push sem PHI e sem conteúdo da notificação interna;
- CSP e políticas de origem compatíveis;
- auditoria da futura sincronização;
- tratamento de sessão expirada durante sync.

## Migrações

A PWA possui migration somente para `PushSubscription`, necessária para armazenar endpoint e material público de criptografia vinculados ao usuário. Manifest, service worker e fila IndexedDB não exigem tabela no servidor.

## Testes

- unitários para helpers, views e políticas;
- Playwright em modo offline e testes de armazenamento cifrado;
- Lighthouse CI >= 90;
- axe-core nas jornadas clínicas;
- testes de segurança garantindo ausência de PHI em cache, IndexedDB em claro e Web Push.

## Rollout

1. Aprovar Spec 014. **Concluído.**
2. Integrar manifest e fallback offline. **Concluído.**
3. Registrar service worker apenas para assets públicos/estáticos. **Concluído.**
4. Adicionar Lighthouse/Playwright. **Concluído.**
5. Habilitar Web Push genérico sem PHI. **Concluído.**
6. Habilitar offline para um único fluxo clínico piloto aprovado. **Pendente de spec clínica.**
7. Validar segurança em dispositivo real e expandir por spec clínica, nunca globalmente.
