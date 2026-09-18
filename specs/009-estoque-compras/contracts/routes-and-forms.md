# Contratos implementados — requisições de materiais

Namespace inventory, sessão Django, reverse/URLs nomeadas.

| Método | Rota | FBV / nome | Template |
|---|---|---|---|
| GET | /estoque/ | item_list | admin/inventory/item_list.html |
| GET | /estoque/requisicoes/ | requisition_list | admin/inventory/requisition_list.html |
| GET/POST | /estoque/requisicoes/nova/ | requisition_create | admin/inventory/requisition_form.html |
| GET | /estoque/requisicoes/<uuid:pk>/ | requisition_detail | admin/inventory/requisition_detail.html |

Todas exigem papel interno e inventory.view_requisitions; criação exige também request_material. Consulta institucional de todos os registros, não filtrada por autor. Sem entrada no PEP. Catálogo/gestão: Django Admin nativo de InventoryItem, sem CRUD alternativo ou Admin de requisições.

## Form

RequisitionForm: item ModelChoiceField de materiais ativos no GET; quantity IntegerField min 1/max 999999; operation_key UUID hidden com uuid4 no GET; confirmed Boolean obrigatório. Label do material: código · nome · unidade. Unidade e snapshots não são campos do POST. Aviso: “Requisição interna — sem reserva, compra ou entrega confirmada”. Botão “Registrar requisição”. Não registrar nomes de pacientes ou justificativas clínicas no catálogo; sem campo livre de observação nesta v1.

No POST, permitir validar identidade de item inativo para retry autorizado; uma operação nova sempre revalida active sob lock. Confirmar também retries. Form inválido retorna 200 preservando chave e erros; sucesso/retry retorna 302 ao detalhe.

## Transação e retry

Validar Forms também na função de domínio, exigir capacidades antes e dentro da transação. Lock do item, set_actor, checar operation_key e equivalência ator/item/quantidade antes de exigir catálogo ativo para novo registro. Retry mantém snapshots originais mesmo após edição/desativação do catálogo; audita ACCESS. Revalidar permissões atuais: retry não contorna revogação.

Nova requisição copia código/nome/unidade sob lock e grava CREATE atômico. Locks serializam o mesmo material; constraint global cobre colisões entre materiais. Recuperar apenas uniq_inventory_req_operation (nome PostgreSQL ou assinatura exata SQLite), após rollback do savepoint. Outra falha de integridade/auditoria não é retry bem-sucedido. Colisão incompatível: 409 sem original. Chave nova: nova requisição.

## Consulta, auditoria e erros

Catálogo só ativos, catálogo/lista 25 por página, page nativo. select_related para item/autor quando renderizados; histórico usa snapshots. ACCESS apenas registros da página ou detalhe. Form GET audita materiais que efetivamente renderiza na seleção; sem auditar catálogo inteiro em páginas de lista. Seleção por ModelChoiceField sem JS; medir custo do catálogo e não declarar paginação do select. Paginação/selector maior exige extensão se volume institucional tornar o select impraticável.

Sem sessão: redirect login; sem papel/capacidade: 403; registro ausente: 404; método: 405; CSRF obrigatório; falha operacional/auditoria: 503 genérico. Namespace todo private/no-store, Vary Cookie, nosniff, inclusive erros/redirects; proteção de POST/variáveis sensíveis.

## PWA e retirada

Network-only. Offline não confirma nem persiste requisição, página privada ou payload; sem fila/sync/push/eventos. Revogar capacidades retira módulo da navegação e bloqueia POST aberto anteriormente. Rollback de código preserva catálogo/requisições/auditoria; reversão de schema apenas em banco descartável. Uso real requer validação institucional do alcance de consulta e unidades.
