# ADR-0006 — Adoção de PWA com Django

## Status
Proposto — aguarda aprovação da Spec 014.

## Contexto

O AegisShare HIS é fullstack, interno e sem API REST pública. Equipes assistenciais precisam usar o sistema em tablets e smartphones, inclusive em áreas com conectividade instável.

## Decisão

Adotar PWA no mesmo monólito Django, com manifest, service worker, IndexedDB controlado e web push. A implementação poderá usar `django-pwa`, `django-webpush`, Workbox e `idb`, após validação de versões e compatibilidade.

Offline será parcial e deny-by-default: apenas fluxos explicitamente aprovados por spec clínica podem persistir payloads locais.

## Consequências

### Positivas
- instalação sem loja;
- atualização junto ao deploy web;
- codebase único;
- melhor experiência móvel e tolerância a conectividade intermitente.

### Negativas
- diferenças de suporte entre Android e iOS;
- complexidade de cache, sessão e sincronização;
- risco adicional de persistência local de dados sensíveis.

### Mitigações
- HTTPS obrigatório;
- nenhuma PHI em texto claro no cache/IndexedDB;
- push genérico sem dados identificáveis;
- limpeza local no logout;
- Lighthouse, Playwright e testes de segurança como gates;
- habilitação offline por fluxo, não globalmente.
