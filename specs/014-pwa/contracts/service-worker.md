# Contrato — Service Worker

## Política padrão

O service worker adota **deny-by-default** para conteúdo autenticado/sensível. Uma rota só pode ser cacheada se sua spec declarar explicitamente a estratégia e demonstrar que não persiste PHI/dados pessoais em texto claro.

| Classe de recurso | Estratégia | Observação |
|---|---|---|
| CSS/JS/fontes/imagens estáticas versionadas | Cache-first | invalidar por versão/hash |
| fallback offline | Cache-first | conteúdo sem dados do usuário |
| HTML público não sensível | Stale-while-revalidate | apenas quando aprovado |
| HTMX autenticado | Network-first ou network-only | fallback somente se contrato permitir |
| prontuário/dados clínicos | Network-only por padrão | exceção exige spec clínica + proteção local |
| páginas administrativas | Network-only | não cachear |
| downloads/documentos | Network-only | não cachear blobs sensíveis |

## Atualização

- versionar caches;
- remover caches obsoletos no `activate`;
- usar `skipWaiting`/`clients.claim` somente com estratégia que evite inconsistência de sessão;
- falhas de atualização não podem apagar payloads offline pendentes antes de sincronização/expiração segura.

## Segurança

- interceptar apenas origem/escopo do AegisShare;
- não cachear respostas `no-store`, downloads ou respostas com dados sensíveis;
- não persistir tokens, cookies ou cabeçalhos de autenticação;
- logout aciona limpeza coordenada dos caches associados à sessão.