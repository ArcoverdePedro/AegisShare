# Contratos implementados — contas em preparação

Namespace billing; sessão Django, URLs internas via reverse/nome.

| Método | Rota | FBV / nome | Template |
|---|---|---|---|
| GET | /faturamento/contas/ | account_list | admin/billing/account_list.html |
| GET/POST | /faturamento/encontros/<uuid:encounter_id>/conta/abrir/ | account_open | admin/billing/account_form.html |
| GET | /faturamento/contas/<uuid:pk>/ | account_detail | admin/billing/account_detail.html |
| GET/POST | /faturamento/contas/<uuid:pk>/itens/novo/ | item_create | admin/billing/item_form.html |

PEP oferece abertura com view_accounts/open_account sem exigir OPEN. GET com conta existente audita ACCESS antes de redirecionar ao detalhe autorizado; POST segue retry/conflito. Menu administrativo só com view_accounts. Não criar escopo financeiro independente do PEP.

## Forms e consulta

AccountOpenForm: operation_key UUID hidden novo por GET; confirmed Boolean “Confirmo a abertura em preparação, sem emissão de cobrança”.

BillingItemForm: description CharField(200), label “Descrição administrativa”; quantity IntegerField 1–999999; unit_price DecimalField(12,2) min 0, label “Valor unitário (BRL)”; operation_key UUID hidden; confirmed Boolean “Confirme os dados manuais; este lançamento não emite cobrança”. Botão “Registrar item”.

Confirmações obrigatórias antes de mutação/retry. Entrada monetária com ponto decimal, localize=False e orientação no formulário; exibição localizada em pt-BR; sem replace arbitrário de vírgulas/pontos, símbolo R$ ou float como fonte do cálculo. Valores inválidos não são arredondados. HTML 200 inválido preserva chave; sucesso/retry 302 ao detalhe.

Lista aceita page. Detalhe pagina 25 itens; “Total em preparação (BRL)” considera todos os itens por agregação, conta vazia 0,00. Aviso de ausência de cobrança; sem atalhos de fechamento/pagamento inexistentes.

## Segurança e mutação

Sem sessão redirect login; profissional/capacidade insuficiente 403; escopo PEP ausente 404; método inadequado 405; CSRF obrigatório. Conflitos 409 genérico sem identificação original; banco/auditoria 503 sem confirmação ou conteúdo identificável. Falha de auditoria de leitura impede entrega. Namespace inteiro private/no-store, Vary Cookie e nosniff; proteger POST/variáveis de exceções.

Abertura: atomic/set_actor, lock do encontro, revalidar capacidades/accessible_patients. operation_key existente exige mesmo ator/encontro e retorna original com ACCESS; encontro ocupado por outra chave retorna 409. Conta e auditoria juntas. Sem exigir OPEN/mudar encontro.

Item: validar form também em chamada interna; atomic/set_actor, lock da conta e revalidar capacidades/escopo. Retry compara ator/conta/descrição trim/inteiro/Decimal e retorna original com ACCESS; novo item/auditoria juntos. Chave nova é lançamento distinto.

Locks serializam mesmo agregado; constraints globais cobrem colisão entre agregados. Recuperar só violação identificada da constraint de operação, fora do savepoint falho, revalidando equivalência. Não converter erro de auditoria/integridade em sucesso. Sem rede/evento na transação. Fechar encontro não fecha/cobra/cria itens.

## Privacidade e retirada

select_related para encontro/paciente/ator renderizados; lista audita contas da página, detalhe conta e itens da página. Agregação não carrega coleção completa nem gera query por item.

Rotas network-only no service worker atual; offline sem confirmação/fila/persistência. Piloto sintético; retirada revoga capacidades e preserva contas/itens/auditoria. Rollback de código preserva dados; reversão de schema apenas em banco descartável.
