# Contratos implementados — pedidos de imagem

Namespace `ris`; sessão Django, sem API pública. URLs internas referenciadas por nomes/reverse, nunca por strings em templates/views.

| Método | Rota | FBV / nome | Template |
|---|---|---|---|
| GET | /imagem/pedidos/ | order_list | clinical/ris/order_list.html |
| GET/POST | /imagem/encontros/<uuid:encounter_id>/pedidos/novo/ | order_create | clinical/ris/order_form.html |
| GET | /imagem/pedidos/<uuid:pk>/ | order_detail | clinical/ris/order_detail.html |

Encontro detalhado do PEP oferece link para novo pedido somente com capacidades de consulta/criação e encontro aberto; o servidor sempre revalida. Não adicionar segunda lista de pedidos ao encontro nesta v1, pois a lista/detalhe RIS já resolve consulta.

## Entrada

`ImagingOrderForm`: `exam` ModelChoiceField, label “Exame de imagem”; `operation_key` UUIDField hidden, inicial UUID novo em cada GET. Nenhum paciente/ator/horário fornecido pelo cliente: o encontro vem da URL autorizada; os demais do servidor. Botão “Registrar pedido de imagem”.

GET oferece somente catálogo ativo. POST deve aceitar UUID de exame existente para reconhecer retry desativado, mas pedido novo exige exame ativo. Nunca recuperar snapshot, autor ou horário do POST. Campo inválido reapresenta HTML 200, preservando chave. Identificador desconhecido retorna erro genérico de seleção; não revelar pedido fora do escopo.

Lista aceita apenas `page`; sem busca livre, estados inexistentes ou filtro que duplique regra de negócio. Paginação 25, `select_related('encounter__patient', 'exam', 'requested_by')` conforme relações realmente utilizadas. Mostrar retrato do exame, paciente autorizado, autor/horário e link ao detalhe. Auditar só itens renderizados. Detalhe mostra protocolo, encontro/paciente, retrato, autor, horário e “Solicitado”; não apresenta atalhos de realização/laudo inexistentes.

## Autorização e respostas

Sem sessão: redirect login. Profissional/capacidade insuficiente: 403. Paciente/pedido/encontro fora de `accessible_patients(user)`: 404. Método inadequado: 405. CSRF mantido em POST. Form inválido: 200. Sucesso ou retry equivalente: 302 ao detalhe autorizado. Encontro fechado, catálogo desativado para pedido novo ou operação incompatível: 409 genérico. Falha de banco/criptografia de infraestrutura/auditoria: não confirmar, retornar 503 sem detalhes internos; o pedido RIS não usa payload cifrado próprio.

Todas as respostas do namespace recebem no-store/private, Vary Cookie e nosniff, inclusive erros antes da FBV. Campos clínicos não aparecem em logs/exceções. Leitura que falha em auditoria não deve entregar conteúdo identificável sem registro.

## Mutação atômica e concorrência

1. Verificar sessão, profissional e as duas capacidades; obter encontro/paciente autorizado.
2. Em `transaction.atomic()` com `set_actor`, bloquear encontro, revalidar escopo/capacidades e exigir OPEN, inclusive para retry.
3. Consultar pedido por operation_key. Se existir, exigir igualdade de ator, encontro e UUID de exame. Incompatibilidade: 409 sem identificadores; equivalência: ACCESS e retorno do original, sem verificar ativo para esse retry.
4. Para pedido novo, bloquear exame e exigir ativo; copiar código/nome do banco e criar com ator/horário do servidor. Auditoria participa da mesma transação.
5. Lock do encontro serializa retries do mesmo encontro. Constraint única protege colisão entre encontros concorrentes. Se uma inserção falhar por unicidade, sair do savepoint antes de consultar; só retornar retry equivalente após autorização. Se não houver pedido equivalente, não converter falha de auditoria/banco em sucesso. Colisões incompatíveis retornam 409; falhas operacionais retornam 503.

Duas operações com chaves novas não são duplicatas. Não deduplicar por nome, exame ou paciente. Não chamar rede na transação nem criar eventos sem consumidor.

## Fronteira PWA e rollout

`/imagem/` exclusivamente network-only no service worker, seguindo o padrão privado existente. POST offline não confirma nem entra em fila. Não guardar telas/pedidos em Cache Storage/IndexedDB/localStorage/sessionStorage; metadados de navegação já existentes não devem carregar conteúdo clínico.

Piloto sintético com catálogo e capacidades atribuídos explicitamente. Para retirar, revogar capacidades e desativar catálogo, preservando pedidos/auditoria. Rollback de código não apaga dados; reversão de schema somente em banco descartável antes do uso real.
