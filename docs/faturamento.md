# Faturamento v1 — contas em preparação

Spec 008 autorizada em 2026-09-18. Nível 1/2/3: reuso, Django nativo e FBVs. Preparação administrativa manual, sem emissão de cobrança ou decisão tarifária.

## Piloto sintético

1. Aplicar migrations, incluindo billing.0001_initial.
2. Atribuir billing.view_accounts para consulta, também billing.open_account para abertura e billing.add_item para lançamento. Profissional interno e escopo PEP continuam obrigatórios; papel ADM clínico não substitui capacidade. Superusuário segue Django com papel interno.
3. Consultar o encontro PEP e usar **Conta em preparação**; confirmar abertura. Uma conta por encontro, sem exigir internação/Admission. Preparação permitida após encerramento/cancelamento clínico, sem mudar encontro ou determinar obrigação de pagamento.
4. Usar **Adicionar item**, informar descrição administrativa, quantidade inteira e preço unitário, confirmar e registrar. Menu **Faturamento** consulta contas; detalhe lista itens e total em preparação.

Moeda única BRL. Quantidade 1–999999; preço 0,00–9999999999,99 com até duas casas. **Na entrada, use ponto decimal**, por exemplo 12.50, sem símbolo/separador de milhares. A exibição segue localização pt-BR. Frações de quantidade, valores não finitos/negativos/excessivos e casas excessivas são rejeitados sem arredondamento. Não inclua identificação de paciente ou texto clínico na descrição.

Subtotal = quantidade × preço; total soma todos os itens da conta, incluindo outras páginas. Conta vazia totaliza 0,00. Valores manuais não são validados contra tarifa e não comprovam realização clínica. Sem importação automática de pedidos/dispensações/atos.

## Reenvio, escopo e erros

Mesmo UUID de operação/ator/encontro retorna conta original. Outra chave para encontro ocupado retorna 409. GET de abertura para encontro com conta existente redireciona ao detalhe autorizado e audita ACCESS antes de redirecionar.

Item com mesma chave/ator/conta/descrição trim/quantidade/preço numericamente equivalente retorna original preservando autor/horário; chave incompatível retorna 409 sem revelar original. Nova chave é item distinto mesmo com conteúdo idêntico. Um novo formulário gera nova chave: consultar registros antes de repetir envio incerto.

Confirmação obrigatória em abertura/item, inclusive retry. Entrada inválida reapresenta form mantendo chave. Falha de banco/auditoria retorna 503 sem confirmar nem deixar registro parcial; leitura sem auditoria não entrega conteúdo. Revogar concessão PEP ou desativar paciente oculta conta/itens e bloqueia envio, inclusive formulário já aberto.

## Privacidade, cálculo e retirada

Contas/itens imutáveis nas entradas da aplicação, sem Admin/edição/exclusão/fechamento. FKs PROTECT preservam registros, sem garantia contra escrita direta no ORM/banco. Auditlog exclui descrição/quantidade/preço dos itens e não copia nome de paciente/total.

Total por agregação ORM: Decimal nativo no PostgreSQL; SQLite usa agregação específica em centavos inteiros para evitar perda monetária e overflow na soma nativa, sem carregar coleção completa. Os preços permanecem limitados ao contrato. Subtotais e total não são persistidos como valores redundantes.

Namespace private/no-store, Vary Cookie e nosniff, incluindo erros/redirects/CSRF. Somente online, sem Cache Storage/IndexedDB/fila/push/WebSocket/evento financeiro. Tentativa offline não confirma registro.

Piloto sintético até validação institucional de catálogo/preço informado, operadores/acesso, conferência, retenção e recuperação. Retirada revoga capacidades preservando contas/itens/auditoria; rollback de código preserva dados. Reverter schema apaga tabelas e só deve ocorrer em banco descartável.

Por YAGNI, sem pagador/convênio/tarifas/guias SUS ou TISS, documento fiscal, cobrança/pagamento, descontos/tributos, fechamento/correção/estorno, quantidades fracionárias, outras moedas ou produção clínica automática. Essas operações dependem de contratos institucionais próprios.

[Evidências](../specs/008-faturamento/validation.md).
