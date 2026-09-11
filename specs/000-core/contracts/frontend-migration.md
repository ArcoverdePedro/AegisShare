# Plano de migração visual: Bulma -> Tailwind CSS + daisyUI

Status: planejamento da Spec 000. Este documento atende T-CORE-11 e **não troca o framework visual neste PR**.

## Contexto atual

O frontend do AegisShare usa `django-simple-bulma`, `crispy-bulma`, `django-crispy-forms`, HTMX, Feather Icons e estilos locais nos templates. O shell global (`templates/navbar/navbar.html`) concentra Bulma, navegação, mensagens, tema claro/escuro e integração PWA. Templates de cadastro/perfil também usam `crispy_forms_tags` e o primeiro cadastro carrega Bulma diretamente.

A migração deve preservar comportamento, acessibilidade, HTMX, CSRF, PWA e limites de segurança. O objetivo não é reescrever views ou regras de negócio junto com CSS.

## Princípios

1. migrar por componente/fluxo, nunca por substituição global em um único PR;
2. manter URLs, names de forms, IDs usados por JavaScript/HTMX e contratos de views estáveis;
3. não alterar autorização para facilitar template;
4. evitar duas folhas globais competindo sobre os mesmos componentes sempre que possível;
5. remover `crispy-bulma` somente depois que todos os forms dependentes tiverem substituto;
6. manter o Django Admin fora do escopo — ele continua com seu tema próprio;
7. PEP clínico é migrado depois dos componentes compartilhados e recebe regressão específica por envolver PHI.

## Arquitetura alvo

```text
Django templates
      |
      +--> componentes compartilhados (shell, alerts, forms, tables, modal, badges)
      |
      +--> Tailwind CSS
      |       +--> tokens/utility classes
      |
      +--> daisyUI
              +--> componentes visuais

HTMX / JavaScript pequeno e explícito continuam responsáveis por interação.
```

A aplicação deve compilar um CSS versionado para `static/`; nenhum CDN de Tailwind/daisyUI deve ser necessário em produção.

## Fundação antes da primeira tela

Criar uma etapa de build frontend reproduzível com versões fixadas. O artefato CSS deve ser gerado antes de `collectstatic` no CI/deploy. A configuração deve incluir somente templates/JS do projeto no content scan para evitar CSS desnecessário.

Definir tokens semânticos para, no mínimo:

- `primary`, `secondary`, `accent`;
- `base-100`, `base-200`, `base-content`;
- `info`, `success`, `warning`, `error`;
- foco/outline e estados disabled;
- superfícies usadas em cards, drop-zone e shell PWA.

O tema atual segue `prefers-color-scheme`. A implementação alvo pode usar `data-theme`, mas deve continuar acompanhando a preferência do sistema por padrão e manter `theme-color`/PWA consistentes.

## Estratégia de coexistência

Durante a transição, Bulma permanece carregado apenas enquanto houver componentes legados. Componentes já migrados devem ficar dentro de uma raiz explícita ou usar classes Tailwind/daisyUI que não dependam de seletores genéricos de Bulma.

Não usar `@apply` para reproduzir toda a API do Bulma. O objetivo é migrar componentes para contratos próprios, não criar uma camada de compatibilidade permanente.

Antes de remover Bulma, a busca no repositório deve confirmar ausência dos principais contratos legados (`navbar-*`, `columns`, `column`, `button is-*`, `notification`, `field`, `control`, `box`, `table`, `modal`, etc.) fora de exceções documentadas.

## Ordem de migração por lote

### Lote 1 — componentes neutros e PWA

- `/offline/` e superfícies PWA genéricas;
- página pública inicial/sobre;
- badges, alerts e cards sem formulário complexo.

Objetivo: validar pipeline CSS, dark mode e Lighthouse sem tocar em fluxos sensíveis.

### Lote 2 — shell global

Migrar `navbar/navbar.html` e extrair componentes compartilhados:

- navegação desktop/mobile;
- menu do usuário;
- mensagens Django/toasts;
- indicador de conectividade PWA;
- card/surface, badge e botão base;
- tema claro/escuro.

O menu mobile e dropdown devem continuar acessíveis por teclado, atualizar `aria-expanded` e fechar de modo previsível.

### Lote 3 — autenticação, setup e perfil

Migrar login, primeiro cadastro, cadastro de usuário, perfil e Segurança.

É o lote que começa a substituir `crispy-bulma`. Para forms, escolher um único padrão:

- templates explícitos de campo reutilizáveis; ou
- `django-crispy-forms` com template pack compatível mantido pelo projeto.

Não manter dois renderizadores de form para o mesmo fluxo. Erros por campo, help text, campos required, estados inválidos e autofocus devem continuar visíveis/acessíveis.

### Lote 4 — documentos

Migrar:

- lista/busca de arquivos e parcial HTMX;
- upload/drop-zone;
- detalhe, versões, comentários e compartilhamento;
- lixeira;
- workspaces/pastas;
- solicitações de documentos;
- notificações.

Preservar os IDs e atributos usados pelas interações de upload, autocomplete, HTMX e ações POST. Mudanças cosméticas não podem transformar POST em GET ou remover CSRF.

### Lote 5 — chat

Migrar lista de conversas, mensagens, estados unread e layout responsivo. Validar atualização em tempo real e rolagem sem alterar autorização de conversation/file.

### Lote 6 — auditoria

Migrar tabela/filtros administrativos próprios do AegisShare. O Django Admin continua fora do escopo.

### Lote 7 — PEP clínico

Migrar pacientes, encontros, evoluções e adendos por último. Esse lote exige regressão de autorização por objeto e verificação de que nenhum conteúdo clínico passa a ser embutido em assets/cache ou exposto em atributos desnecessários do DOM.

## Testes de regressão por componente

Cada lote deve incluir pelo menos:

- testes Django existentes para status/autorização e formulários;
- Playwright para jornada principal desktop e viewport mobile;
- assertions de elementos funcionais por role/label, evitando depender apenas de classes CSS;
- navegação por teclado para menu/modal/form relevante;
- dark/light mode onde o componente aparece no shell;
- HTMX/JS funcional quando houver;
- Lighthouse CI sem regressão além dos thresholds definidos no projeto.

Snapshots visuais podem complementar a suíte, mas não substituem asserts funcionais/acessibilidade. Se snapshots forem adotados, devem usar viewport/browser fixos e atualização explícita em PR.

## Critério de aceite por lote

Um lote só remove suas classes/dependências Bulma quando:

1. todas as telas do lote usam os componentes alvo;
2. desktop e mobile foram exercitados em Playwright;
3. foco, labels, erros e estados disabled foram verificados;
4. HTMX/JS associados continuam funcionando;
5. testes de autorização do fluxo continuam passando;
6. Lighthouse/CI passam;
7. não há dependência Bulma oculta no partial migrado.

## Remoção final de dependências

Somente depois da busca de referências e de todos os lotes concluídos:

- remover `{% load django_simple_bulma %}` / `{% bulma %}`;
- remover `django-simple-bulma` de `pyproject.toml`/lock;
- remover `crispy-bulma` quando nenhum form o usar;
- revisar `CRISPY_TEMPLATE_PACK`/settings;
- remover CSS de compatibilidade e estilos locais que tenham equivalente nos componentes alvo;
- executar `collectstatic`, Playwright, Lighthouse e suíte Django completa.

A remoção das dependências deve ser PR separado do último grande lote visual para facilitar rollback.

## Rollback

Cada lote deve ser reversível isoladamente. Enquanto Bulma coexistir, rollback consiste em restaurar o template/componente legado daquele lote sem mudança de view/model. Após a remoção final das dependências, o commit anterior à remoção deve continuar sendo um ponto de rollback funcional até a estabilização da release.

## Fora do escopo deste plano

- redesenho de regras de negócio;
- troca de HTMX por SPA;
- migração do Django Admin;
- mudança de rotas/contratos HTTP;
- alteração de autorização ou cache PWA para acomodar o CSS.

Essas separações mantêm a migração visual mensurável e evitam que regressões de UI sejam confundidas com mudanças funcionais ou clínicas.
