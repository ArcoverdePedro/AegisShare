# Spec 009 — Estoque e Compras v1: catálogo e requisições internas

## Status

**Recorte autorizado e implementado em 2026-09-18.** O usuário respondeu “[@Ponytail] continue com o SDD” à pergunta de aprovação do catálogo e requisições apresentada na resposta anterior.

## Recorte e histórias

A fase 4 continua por um catálogo institucional de materiais **não medicamentosos** e requisições internas de um material por registro. A requisição expressa uma necessidade; não confirma disponibilidade, reserva, compra, entrega ou consumo. O estoque farmacêutico da Spec 003 continua como fonte de seus próprios lotes e movimentos.

Como operador interno autorizado, quero solicitar quantidade inteira de um material ativo e reconhecer reenvios sem duplicação. Como auditor, quero conservar o material/unidade solicitados mesmo após alterações do catálogo.

O recorte autorizado adota consulta institucional de todos os registros deste módulo por capacidade explícita, sem dados de paciente, vínculo PEP ou escopo por setor nesta v1. Esse alcance foi autorizado; unidades/setores com segregação exigem extensão anterior ao uso correspondente. Piloto sintético até validação institucional do catálogo e das unidades.

## Requisitos funcionais

- **RF-INV-01:** InventoryItem com UUID, código único até 64 caracteres, nome até 200, unidade de contagem até 40 e active. Strings obrigatórias com trim externo; código comparado exatamente, sem normalização implícita de caixa. A unidade é definida pelo catálogo (ex.: caixa); não converter embalagens, doses ou frações. Sem quantidade disponível, preço ou ponto de pedido fictício.
- **RF-INV-02:** Requisition com UUID, FK PROTECT para InventoryItem, snapshots de código/nome/unidade, quantidade inteira 1–999999, autor/horário do servidor e operation_key global única. Um registro por material; não criar carrinho/itens de pedido sem necessidade concreta. Histórico append-only nas entradas da aplicação; sem edição, exclusão ou estados artificiais.
- **RF-INV-03:** sessão e is_internal_professional em todas as superfícies; inventory.view_requisitions para consulta de catálogo/requisições/detalhe; criação também exige inventory.request_material. Consulta institucional, sem grants automáticos a grupos. Papel ADM não substitui capacidade; superusuário segue Django com papel interno. Gestão do catálogo via Admin nativo requer staff, papel interno e permissões inventory de modelo.
- **RF-INV-04:** criação atomic/set_actor, lock do material, revalidar capacidades e catálogo ativo antes de novo registro. Snapshot vem do banco sob lock, nunca do POST. Confirmação obrigatória e validação Forms também em chamada interna.
- **RF-INV-05:** retry de mesma chave/ator/material/quantidade retorna original com ACCESS, sem mudar horário ou snapshots; é permitido após renomeação ou desativação do material se o operador continuar autorizado. Outra chave é solicitação distinta, mesmo com conteúdo igual. Colisão incompatível retorna 409 genérico sem expor original. Concorrência coberta por constraint global e recuperação apenas da violação identificada dessa constraint, fora do savepoint falho.
- **RF-INV-06:** catálogo e lista paginados em 25, relacionados obtidos sem N+1. Catálogo público interno mostra apenas ativos; detalhe/lista histórica mostram snapshots, inclusive de material atualmente inativo. Menu Estoque com capacidade de consulta. Nenhuma conexão automática com farmácia, faturamento ou pedidos cirúrgicos.
- **RF-INV-07:** CREATE/ACCESS com ator; auditar somente registros efetivamente renderizados e requisição no detalhe. Criação/auditoria atômicas; falha reverte criação. Falha de leitura auditada impede entrega. Auditlog exclui textos do catálogo/snapshots e quantidade; logs não copiam esses campos. Admin mantém auditoria nativa e registro de mudanças via auditlog sem duplicar textos em logs genéricos.

## Requisitos não funcionais

- **RNF-INV-01:** apps.admin.inventory, label inventory, duas tabelas, Forms/FBVs/DTL; reutilizar usuário, papel interno, auditlog, layout, middleware e CI. Sem dependência nova, JS próprio, fila, serviço em classe ou API REST pública.
- **RNF-INV-02:** namespace /estoque/ private/no-store, Vary Cookie, nosniff em respostas, redirects e erros; CSRF e proteção de POST/variáveis sensíveis de exceções. Conflitos sem IDs de outros registros; falha operacional/auditoria 503 sem confirmação parcial.
- **RNF-INV-03:** online apenas, sem Cache Storage/IndexedDB de páginas ou formulários privados, sem fila/PWA sync/push. Telefone/tablet sem overflow, labels acessíveis, axe sem violações sérias/críticas.
- **RNF-INV-04:** migration versionada e reversível; concorrência PostgreSQL real; lint/check/migrations/testes/E2E/SAST/SCA com evidências. Lighthouse com URL e avisos reais, sem afirmar meta atingida por execução bem-sucedida.

## Fora de escopo

Medicamentos, saldos, lotes/validade, entradas/saídas, recebimento, reservas, transferências, atendimento/cancelamento/correção de requisições, setores/almoxarifados segregados, Supplier, PurchaseOrder, preços/orçamentos/pagamentos, ponto de pedido e reposição automática.

Movimentação exige contrato de unidade, lote/localização, saldo não negativo, concorrência, ajustes e rastreabilidade. Compras exigem fornecedor, autorização, recebimento parcial e efeitos financeiros. Integração farmacêutica exige uma fonte de verdade explícita, preservando StockItem/Lot/StockMovement existentes. Não criar eventos inventory.moved/purchase.created/purchase.received sem produtor real e consumidor contratado.

## Rastreabilidade implementada

| Requisito | Rota/FBV | Template | Critério/teste executado |
|---|---|---|---|
| 01/03/06 | item_list | admin/inventory/item_list.html | CA-INV-01, CA-INV-02, CA-INV-05 |
| 02/03/04 | requisition_create | admin/inventory/requisition_form.html | CA-INV-02, CA-INV-03 |
| 02/05/06 | requisition_list/detail | admin/inventory/requisition_list.html e requisition_detail.html | CA-INV-04, CA-INV-05 |
| 07/RNF-02 | todas/Admin | templates acima/Admin nativo | CA-INV-06 |
| RNF-03/04 | namespace e CI | layout/PWA existente | CA-INV-07 |

[Inventário](research.md), [modelo](data-model.md), [contratos](contracts/routes-and-forms.md), [plano](plan.md), [tarefas](tasks.md), [aceitação](features/requisitions.feature). [Evidências executadas](validation.md) e [guia operacional](../../docs/estoque-requisicoes.md).

## Definition of Done

- [x] Inventário, recorte, modelo, contratos, plano, tarefas e aceitação.
- [x] Aprovação: materiais não medicamentosos, uma linha por requisição, inteiros e consulta institucional por capacidade.
- [x] App/modelos/Admin/Forms/FBVs/migration e privacidade.
- [x] Snapshots/retries/concorrência/rollback/permissões com testes reais.
- [x] E2E/mobile/axe/offline/gates com evidências e guia operacional.
- [ ] Validação institucional antes do uso real.

Meta de desempenho Lighthouse da baseline pendente: 73/100 na página inicial. Não se declara DoD institucional integral.
