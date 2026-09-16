# Rotas — Spec 013 v1

Namespace `compliance`. Todas são internas, sessão Django e profissional interno. Todas exigem `compliance.view_requests`; criação/transição exigem capacidade adicional e escopo PEP atual.

| Método | URL | FBV/nome | Template | Capacidade adicional |
|---|---|---|---|---|
| GET | `/lgpd/solicitacoes/` | `request_list` | `compliance/request_list.html` | nenhuma |
| GET/POST | `/lgpd/solicitacoes/nova/` | `request_create` | `compliance/request_form.html` | `register_request` |
| GET | `/lgpd/solicitacoes/<uuid:pk>/` | `request_detail` | `compliance/request_detail.html` | nenhuma |
| GET/POST | `/lgpd/solicitacoes/<uuid:pk>/transicao/` | `request_transition` | `compliance/request_transition.html` | `process_request` |

POSTs exigem CSRF. Sucesso: redirect 302 ao detalhe. Erro de form: HTML 200 com erros. Estado desatualizado/transição incompatível: HTML 409, sem mutação. Objeto fora do escopo: 404; falta de capacidade: 403; método não permitido para usuário autenticado: 405. Sem sessão: login.

GET de transição de solicitação encerrada redireciona ao detalhe com mensagem informativa; POST sobre ela retorna 409. Nenhuma ação mutante em GET.

Cabeçalhos: `Cache-Control: private, no-store`, `Vary: Cookie`, `X-Content-Type-Options: nosniff`, incluindo erros e redirects.

Query string aceita apenas `status` e `page`; estado desconhecido retorna filtro inválido sem ampliar o queryset. IDs sensíveis não são usados como filtro livre nem incorporados à telemetria de negócio. URLs internas por `reverse()`/`{% url %}`.
