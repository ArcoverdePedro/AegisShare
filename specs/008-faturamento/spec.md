# Spec 008 — Faturamento v1: preparação manual de contas

## Status

**Autorizada e implementada em 2026-09-18.** O usuário respondeu “[@Ponytail] continue” à pergunta de aprovação deste recorte concreto. Evidências locais em [validation.md](validation.md).

## Recorte e user stories

A fase 4 do roadmap começa pelo faturamento. Esta v1 permite abrir uma conta administrativa por encontro PEP e registrar itens manuais para conferência. Não emite cobrança, documento fiscal, guia, autorização ou confirmação de pagamento.

Como operador autorizado, quero preparar conta e itens com total exato, preservar autoria e reconhecer reenvios sem duplicação. Como auditor, quero rastrear criação/consulta sem copiar descrições ou valores para logs genéricos.

O piloto adota **BRL**, quantidades inteiras positivas, preços unitários não negativos com duas casas decimais e uma conta por encontro. Preparação continua permitida após encerramento clínico. Esses limites foram autorizados neste contrato; não constituem política de preço ou obrigação de pagamento.

## Requisitos funcionais

- **RF-BILL-01:** HospitalAccount único por pep.Encounter, UUID, autor/horário do servidor e operation_key único. Paciente vem do encontro. Exibir “Em preparação — sem cobrança emitida”, sem campo de estado redundante. Não exigir Admission ADT nem duplicar paciente/pagador/convênio.
- **RF-BILL-02:** BillingItem append-only vinculado à conta, descrição obrigatória até 200 caracteres (trim externo), quantidade inteira 1–999999 e preço unitário 0,00–9999999999,99 BRL com no máximo duas casas. Ator/horário do servidor e operation_key único no conjunto de itens. Não colocar identificação de paciente ou justificativa clínica na descrição.
- **RF-BILL-03:** subtotal = quantidade × preço; total = soma dos subtotais, no servidor, com Decimal/ORM. Sem float, arredondamento de entrada inválida ou totais persistidos redundantes. Conta vazia totaliza 0,00. Não inferir tarifas ou importar atos clínicos automaticamente.
- **RF-BILL-04:** sessão, profissional interno, billing.view_accounts e accessible_patients(user) em todas as superfícies identificáveis. Abrir exige também billing.open_account; lançar exige também billing.add_item. Capacidades não concedem escopo PEP. ADM clínico não substitui capacidade; superusuário segue Django com requisito de papel interno.
- **RF-BILL-05:** revalidar escopo/capacidades sob lock. Encerramento/cancelamento clínico não fecha conta nem bloqueia preparação administrativa enquanto o paciente estiver acessível; não mudar encontro. Paciente inativo/concessão revogada oculta dados e bloqueia envio, inclusive formulário já aberto.
- **RF-BILL-06:** abertura equivalente (chave/ator/encontro) retorna original com ACCESS. Outra chave para encontro ocupado ou chave incompatível: 409 genérico. Retry de item exige mesma chave/ator/conta/descrição trim/quantidade/preço Decimal; preserva dados e audita ACCESS. Nova chave de item é lançamento distinto mesmo com conteúdo idêntico.
- **RF-BILL-07:** lista de contas e itens do detalhe paginados em 25. Total no detalhe considera todos os itens da conta por agregação, não apenas a página. Lista sem total por conta em loop. Entrada pelo encontro/menu administrativo. Sem edição/exclusão/fechamento ou Admin de contas/itens. FKs PROTECT e guardas das entradas preservam histórico, sem garantia contra escrita direta no ORM/banco.
- **RF-BILL-08:** criação e auditoria atômicas; falha reverte mutação. Auditar CREATE/ACCESS com ator. Lista apenas contas renderizadas; detalhe conta e itens renderizados. Agregação total não expõe descrição/IDs de outras páginas. Falha de auditoria de leitura impede entrega identificável. Auditlog exclui descrição/quantidade/preço; logs não copiam nomes de paciente, valores ou total.

## Requisitos não funcionais

- **RNF-BILL-01:** apps.admin.billing, label billing, conforme contexto administrativo do SDD; duas tabelas, Forms, FBVs e DTL. Reusar PEP/usuário/auditlog/layout/middleware. Sem dependência nova, SPA, JS próprio, service class, worker ou fila.
- **RNF-BILL-02:** /faturamento/ private/no-store, Vary Cookie e nosniff, inclusive redirects/CSRF/erros. Proteger POST/variáveis sensíveis de exceções; conflitos não revelam original. Sem API REST pública.
- **RNF-BILL-03:** somente online; sem Cache Storage/IndexedDB/fila/push/WebSocket/evento sem consumidor. Telefone/tablet sem overflow, labels acessíveis e axe sem violações sérias/críticas.
- **RNF-BILL-04:** select_related, paginação antes de ACCESS e total por ORM tipado Decimal, sem coleção completa ou queries por item. Migration reversível, concorrência PostgreSQL e rollback com evidências reais. Avisos Lighthouse não significam meta atingida.

## Fora de escopo e gates posteriores

Insurance, SUSGuide/AIH/TISSGuide, Glosa, preços/tabelas SUS/convênio, cobrança/pagamento/reembolso, descontos/tributos/documento fiscal, fechamento/reabertura/correção/estorno, quantidades fracionárias, outras moedas, anexos/exportação e produção clínica automática.

Fechamento exige política institucional de conferência/aprovação/correção e efeitos financeiros. Tarifas/guias/exportações exigem fontes/versionamento e contratos reais. Integração clínica precisa definir atos efetivamente realizados e correções sem duplicação: pedidos LIS/RIS/cirúrgicos não provam realização. Não alterar estoque/dispensação.

Eventos do roadmap (account.opened/closed, billing.exported, glosa.received) somente em extensão com consumidor e contrato mínimo após commit. Nenhuma decisão jurídica/financeira automatizada. Piloto sintético até validação institucional de uso real.

## Rastreabilidade implementada

| Requisito | Superfície | Aceitação |
|---|---|---|
| 01/04/05 | account_open / account_form | CA-BILL-01/02 |
| 02/03/04/05 | item_create / item_form | CA-BILL-02/03 |
| 06/07 | mutações, locks e constraints | CA-BILL-04 |
| 03/07/08 | account_list/detail e templates | CA-BILL-03/05/06 |
| 08/RNF-02/03/04 | auditoria/middleware/PWA/gates | CA-BILL-06/07 |

[Modelo](data-model.md), [contratos](contracts/routes-and-forms.md), [inventário](research.md), [plano](plan.md), [tarefas](tasks.md), [aceitação](features/accounts.feature). [Evidências executadas](validation.md) e [guia operacional](../../docs/faturamento.md).

## Definition of Done

- [x] Recorte, inventário, modelo, contratos, plano, tarefas e aceitação.
- [x] Aprovação explícita: BRL, inteiros, conta única por encontro e preparação após encerramento clínico.
- [x] Implementação/migration reversível e testes de cálculo/validação/escopo/retries.
- [x] Concorrência PostgreSQL, auditoria/rollback e privacidade.
- [x] E2E/revogação real/mobile/axe/offline/gates com evidências.
- [x] Guia operacional/rastreabilidade executável.
- [ ] Validação institucional antes de uso real.
