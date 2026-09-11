# Spec 014 — PWA: Progressive Web App

## Contexto

O AegisShare HIS deve ser instalável em smartphones e tablets e continuar útil em conectividade intermitente, sem criar app nativo ou API REST pública. A PWA é uma camada de apresentação do mesmo monólito Django.

## User Stories

- Como profissional assistencial, quero instalar o AegisShare na tela inicial do dispositivo.
- Como enfermeiro, quero abrir telas críticas previamente preparadas mesmo sem conexão.
- Como profissional, quero que ações offline autorizadas sejam sincronizadas quando a rede retornar.
- Como usuário, quero que a interface acompanhe o tema claro/escuro do dispositivo.
- Como profissional autorizado, quero receber push de alertas sem exposição de dados clínicos identificáveis.

## Requisitos Funcionais

- **RF-PWA-01** Instalação em Android e iOS via navegador.
- **RF-PWA-02** Offline parcial para telas críticas explicitamente autorizadas por spec.
- **RF-PWA-03** Sincronização idempotente de payloads pendentes quando a conexão retornar.
- **RF-PWA-04** Push notifications para alertas aprovados, sem PHI identificável no conteúdo.
- **RF-PWA-05** Tela de fallback offline personalizada.
- **RF-PWA-06** Modo `standalone`.
- **RF-PWA-07** Respeitar `prefers-color-scheme` e mudanças de tema do dispositivo.
- **RF-PWA-08** Logout deve invalidar/limpar caches e dados locais sensíveis associados à sessão.

## Requisitos Não Funcionais

- **RNF-PWA-01** HTTPS obrigatório fora de localhost.
- **RNF-PWA-02** Service Worker com política de cache documentada por classe de recurso.
- **RNF-PWA-03** IndexedDB apenas para payloads offline explicitamente permitidos e protegidos.
- **RNF-PWA-04** Manifest com nome, ícones 192/512, tema, display e start URL.
- **RNF-PWA-05** Lighthouse PWA >= 90.
- **RNF-PWA-06** Carregamento offline de telas em cache <= 3s em dispositivo-alvo razoável.
- **RNF-PWA-07** Sincronização idempotente e conflitos auditáveis.
- **RNF-PWA-08** Dados sensíveis não podem ser persistidos em texto claro em cache/IndexedDB.

## Critérios de Aceitação

```gherkin
Cenário: Instalar AegisShare no Android
  Dado que um profissional acessa o AegisShare via Chrome
  Quando instala o aplicativo a partir do navegador
  Então o ícone aparece na tela inicial
  E a aplicação abre em modo standalone
```

```gherkin
Cenário: Registrar dado crítico offline autorizado
  Dado que a tela foi previamente disponibilizada para offline
  E o usuário está autenticado em uma sessão válida
  Quando a conexão cai e o usuário envia um formulário offline permitido
  Então o payload é armazenado localmente de forma protegida
  E fica com status pendente
  E ao restabelecer a conexão a sincronização é tentada de forma idempotente
  E o resultado é auditado
```

```gherkin
Cenário: Tema acompanha o dispositivo
  Dado que o AegisShare está aberto
  Quando o sistema operacional muda entre tema claro e escuro
  Então a interface atualiza sem exigir novo login
  E mantém contraste compatível com WCAG 2.1 AA
```

## Telas e Fluxos

- fallback offline;
- fluxo de instalação/manifest;
- feedback de conectividade e itens pendentes;
- telas críticas declaradas por cada spec clínica;
- configuração de notificações push.

## Fora de Escopo

- app nativo;
- publicação em lojas;
- acesso avançado a hardware;
- offline completo do HIS;
- WebSocket funcionando offline.

## Dependências

Specs 000 Core, 001 PEP, 002 ADT e 004 Enfermagem conforme cada fluxo for implementado.

## Riscos

- limitações de Background Sync e push no iOS;
- persistência indevida de dados clínicos;
- service worker desatualizado;
- conflitos de sincronização;
- cache acidental de páginas administrativas ou prontuários.

## Rastreabilidade

| Requisito | Rota/View | Template/Asset | Teste |
|---|---|---|---|
| RF-PWA-01 | manifest/service worker | manifest + ícones | Playwright/Lighthouse |
| RF-PWA-02 | `/offline/` + rotas permitidas | `pwa/offline.html` | E2E modo offline |
| RF-PWA-03 | views internas sincronizáveis | `sync.js` | pytest-bdd + E2E |
| RF-PWA-04 | fluxo interno webpush | service worker | unit + E2E quando suportado |
| RF-PWA-05 | `/offline/` | `pwa/offline.html` | E2E |
| RF-PWA-07 | todas as telas | CSS/theme tokens | a11y + E2E |
| RF-PWA-08 | logout | SW/IndexedDB | security test |
