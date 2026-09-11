# Plano Técnico — Spec 014 PWA

## Arquitetura

Criar `apps/pwa` dentro do monólito. Manifest, service worker, fallback offline, IndexedDB helpers e sincronização pertencem ao mesmo deploy Django.

## Dependências planejadas

- `django-pwa`;
- `django-webpush`;
- Workbox 7.x;
- `idb` 8.x.

A inclusão efetiva de dependências ocorrerá somente após aprovação desta spec.

## Rotas e Views

- `/offline/` para fallback;
- manifest e service worker servidos conforme integração escolhida;
- sincronização reutiliza views/formulários internos existentes e autenticados sempre que tecnicamente seguro, sem endpoint REST público.

## Estratégia de Cache

Definida em `contracts/service-worker.md`. Por padrão, dados clínicos e páginas administrativas são `network-only` até que uma spec declare explicitamente uma exceção segura.

## IndexedDB e Sincronização

Definidos em `contracts/offline-sync.md`. Payloads offline críticos devem ser minimizados, protegidos e associados a idempotency keys.

## Push Notifications

Mensagens push devem ser genéricas, sem nome de paciente, diagnóstico, medicamento ou outro dado clínico identificável. O deep link exige autenticação e revalidação de autorização ao abrir.

## Tema e Acessibilidade

O sistema deve respeitar `prefers-color-scheme`, manter tokens de cor coerentes e cumprir WCAG 2.1 AA. Componentes offline/standalone devem usar os mesmos tokens de tema.

## Segurança e LGPD

- HTTPS obrigatório;
- service worker limitado ao escopo do app;
- limpeza de dados locais no logout;
- evitar cache de PHI;
- CSP e políticas de origem compatíveis;
- auditoria da sincronização;
- tratamento de sessão expirada durante sync.

## Migrações

Nenhuma migration obrigatória apenas para manifest/SW. Modelos de push ou fila offline no servidor só serão adicionados se necessários e após contrato de dados.

## Testes

- unitários para helpers e políticas;
- pytest-bdd para sync;
- Playwright em modo offline;
- Lighthouse CI >= 90;
- axe-core;
- testes de segurança garantindo ausência de PHI em caches/push.

## Rollout

1. Aprovar Spec 014.
2. Integrar manifest e fallback offline.
3. Registrar service worker apenas para assets públicos/estáticos.
4. Adicionar Lighthouse/Playwright.
5. Habilitar offline para um único fluxo clínico piloto aprovado.
6. Validar segurança em dispositivo real.
7. Expandir por spec clínica, nunca globalmente.