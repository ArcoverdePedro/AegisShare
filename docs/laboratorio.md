# Laboratório — pedidos e coleta (LIS v1)

## Ativação

Execute `uv run python manage.py migrate`. A migration `lis.0001_initial` cria catálogo, pedidos, amostras e permissões; nenhuma capacidade é atribuída automaticamente.

No Django Admin, cadastre exames em **Laboratório → Lab tests**, com código único, nome, material e situação ativa. A manutenção exige profissional interno, acesso staff ao Admin e permissões nativas de LabTest. Não há catálogo clínico pré-carregado; a instituição é responsável pelo conteúdo aprovado.

Atribua capacidades aos profissionais/grupos apropriados:

| Capacidade | Uso |
|---|---|
| `lis.view_orders` | lista, detalhe e pré-requisito das ações |
| `lis.order_test` | solicitar exame em encontro aberto |
| `lis.collect_specimen` | registrar coleta em encontro aberto |

Capacidades não concedem acesso ao paciente. Em cada operação, o usuário deve ser profissional interno e o paciente deve estar no escopo PEP atual. Pacientes inativos continuam fora desse escopo.

## Operação

Abra um encontro no PEP e escolha **Solicitar exame**. Selecione um exame ativo; o pedido preserva código/nome/material, encontro, autor e horário. O menu **Clínico → Laboratório** lista apenas pedidos acessíveis.

Abra o pedido, escolha **Registrar coleta**, informe código e data/hora no fuso configurado do servidor e confirme a conferência física de paciente, pedido e amostra. O horário não pode anteceder o pedido ou estar no futuro. Código de amostra tem até 64 caracteres, remove espaços externos e distingue maiúsculas de minúsculas.

Há um exame e no máximo uma coleta por pedido. A situação “Coleta registrada” é derivada da amostra; não significa recebimento, aceitação ou resultado liberado. Alterar/desativar o catálogo não modifica pedidos anteriores.

Reenviar o mesmo formulário com os mesmos dados e autorização vigente recupera o registro original. Alterar o conteúdo mantendo a chave, reutilizar código indisponível ou tentar outra coleta para o pedido retorna conflito, sem sobrescrever histórico. Um novo formulário de pedido recebe nova chave e representa outro pedido.

Após falha de conexão, consulte o histórico: a resposta pode ter sido perdida após uma gravação concluída. O fluxo exige conexão e não usa fila offline, cache clínico ou push.

## Limites do piloto

Utilize dados sintéticos até aprovação institucional do catálogo e do procedimento operacional. Não há edição, cancelamento, correção, recoleta, múltiplas amostras, etiquetas, resultados, laudos ou integração com equipamento nesta versão. Os fluxos de exceção necessários ao uso real precisam de extensão aprovada.

A auditoria genérica preserva IDs, atores e ações, sem copiar nome de exame, material ou código de amostra. Histórico protegido pela aplicação não impede alteração direta por administrador do banco.

## Validação e retirada

```bash
uv run python manage.py test apps.clinical.lis
uv run python tests/e2e/prepare_lis_journeys.py
npx playwright test tests/e2e/lis_journeys.spec.js
```

Use PostgreSQL descartável para testar concorrência. A preparação E2E cria credenciais públicas e dados sintéticos; execute somente em ambiente de teste com servidor e administrador inicial configurados.

Para retirar o piloto, revogue capacidades e remova os links pelo rollback do código, preservando tabelas. A reversão `migrate lis zero` apaga registros e foi validada somente em banco descartável. Não a use após dados reais.

[Spec](../specs/005-lis/spec.md) · [Evidências](../specs/005-lis/validation.md).

## Fase pré-analítica (H14)

- Pedido → amostra(s) → eventos. Uma amostra vigente por pedido; `accession_code` é único e nunca reaproveitado.
- `/laboratorio/recebimento/` (`lis.receive_specimen`): a leitura do código confirma só a chegada ao laboratório. Amostra já recebida, rejeitada ou de pedido cancelado é recusada (409).
- Rejeição com motivo (texto livre; catálogo de motivos aguarda G07) mantém a amostra e o evento; o pedido fica "aguardando recoleta" e a nova coleta liga-se à rejeitada (`replaces`).
- Cancelamento (`lis.cancel_order`) com motivo; amostra recebida precisa ser rejeitada antes. Eventos e cancelamentos são append-only.
- Etiqueta imprimível (código, paciente, nascimento, exame, material) em `/laboratorio/pedidos/<id>/etiqueta/`; código de barras/impressora térmica não implementados.
- Pendentes (G07): múltiplos materiais por pedido, transporte/lotes de envio, catálogo de motivos de rejeição e critérios de aceitação.

## Resultados manuais (H15)

- `lis.enter_result` registra resultado em amostra recebida e não rejeitada: analito, valor (texto, como emitido), unidade, referência informada e método. Nada é calculado ou interpretado; não há sinalização de crítico (G07).
- `lis.validate_result` valida e depois libera. Só resultado liberado aparece a quem tem apenas `lis.view_orders`.
- Retificação cria nova versão ligada à liberada (`supersedes`) com motivo; a original permanece intacta. Conteúdo do resultado é imutável. `operation_key` evita duplicidade em reenvio.
- Pendentes: catálogo de analitos/unidades, valores críticos e ciência (G07), importação HL7/ASTM a partir da caixa em quarentena (G07/G11), assinatura do laudo (H06/G05).
