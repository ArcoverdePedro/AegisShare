# Tasks — Spec 014 PWA

> Spec aprovada em 2026-09-11. Implementação liberada conforme ADR-0006 e contratos da Spec 014.

- [x] **T-PWA-01** Registrar ADR de adoção de PWA e limites de offline. RF-PWA-01/02.
- [ ] **T-PWA-02** Adicionar dependências PWA/webpush após validação de compatibilidade. RF-PWA-01/04. Manifest/SW básicos foram implementados sem dependência extra; webpush permanece pendente.
- [x] **T-PWA-03** Implementar manifest e ícones PNG 192/512. RF-PWA-01/06.
- [x] **T-PWA-04** Implementar service worker com política deny-by-default para conteúdo sensível. RNF-PWA-02/08.
- [x] **T-PWA-05** Implementar `/offline/` e fallback visual. RF-PWA-05.
- [ ] **T-PWA-06** Criar helpers IndexedDB e criptografia/proteção de payloads permitidos. RNF-PWA-03/08.
- [ ] **T-PWA-07** Implementar fila idempotente de sincronização para um fluxo piloto aprovado. RF-PWA-03.
- [x] **T-PWA-08** Implementar limpeza de cache/IndexedDB no logout. RF-PWA-08.
- [ ] **T-PWA-09** Configurar push genérico sem PHI. RF-PWA-04.
- [x] **T-PWA-10** Garantir tema claro/escuro consistente em standalone/offline. RF-PWA-07.
- [ ] **T-PWA-11** Adicionar Playwright offline e Lighthouse CI. RNF-PWA-05/06.
- [ ] **T-PWA-12** Executar testes de segurança completos para caches, IndexedDB e push. RNF-PWA-08. A fundação já possui testes unitários de manifest, fallback, cache deny-by-default e limpeza no logout.
