# Tasks — Spec 014 PWA

> Spec aprovada em 2026-09-11. Implementação liberada conforme ADR-0006 e contratos da Spec 014.

- [x] **T-PWA-01** Registrar ADR de adoção de PWA e limites de offline. RF-PWA-01/02.
- [x] **T-PWA-02** Adicionar dependências PWA/webpush após validação de compatibilidade. RF-PWA-01/04. Manifest/SW permanecem nativos do monólito; Web Push usa `pywebpush>=2.5,<3` conforme ADR-0007, evitando wrapper Django desnecessário.
- [x] **T-PWA-03** Implementar manifest e ícones PNG 192/512. RF-PWA-01/06.
- [x] **T-PWA-04** Implementar service worker com política deny-by-default para conteúdo sensível. RNF-PWA-02/08.
- [x] **T-PWA-05** Implementar `/offline/` e fallback visual. RF-PWA-05.
- [x] **T-PWA-06** Criar helpers IndexedDB e criptografia/proteção de payloads permitidos. RNF-PWA-03/08. `static/pwa/offline_queue.js` mantém somente ciphertext AES-GCM no IndexedDB, usa chave não extraível, associa o envelope a `idempotency_key`, operação e fingerprint de sessão e não ativa sincronização automaticamente.
- [ ] **T-PWA-07** Implementar fila idempotente de sincronização para um fluxo piloto aprovado. RF-PWA-03. A fila local protegida está pronta, mas nenhum fluxo clínico é habilitado enquanto a spec correspondente não aprovar o piloto e seu contrato de conflito/sincronização.
- [x] **T-PWA-08** Implementar limpeza de cache/IndexedDB no logout. RF-PWA-08.
- [x] **T-PWA-09** Configurar push genérico sem PHI. RF-PWA-04. `PushSubscription`, VAPID e `pywebpush` publicam sem payload; título/corpo/destino ficam fixos no service worker, o vínculo da sessão é armazenado apenas como SHA-256 e o logout revoga somente o dispositivo/sessão encerrado antes de reabrir `/notificacoes/` autenticado.
- [x] **T-PWA-10** Garantir tema claro/escuro consistente em standalone/offline. RF-PWA-07.
- [x] **T-PWA-11** Adicionar Playwright offline e Lighthouse CI. RNF-PWA-05/06. Playwright valida manifest, service worker, fallback offline e ausência de rotas sensíveis no cache; Lighthouse CI aplica gates às categorias atuais de qualidade web.
- [x] **T-PWA-12** Executar testes de segurança completos para caches, IndexedDB e push. RNF-PWA-08. A suíte cobre cache deny-by-default, limpeza no logout, IndexedDB cifrado, idempotência local, ausência de payload no Web Push, cópia genérica fixa no service worker, revogação da sessão atual e subscriptions expiradas (404/410).
