# Contrato de Formulários — Spec 003 Prescrição e Farmácia

## MedicationRequestCreateForm

| Campo | Tipo | Regra |
|---|---|---|
| `encounter` | ModelChoice | somente encontros abertos de pacientes no escopo PEP do usuário; label inclui paciente/tipo/data para decisão humana |
| `replaces` | UUID/hidden opcional | somente prescrição do mesmo encontro e acessível; service revalida |

Permissão: `prescription.prescribe_medication` + escopo PEP. O paciente é derivado do `Encounter` e não pode ser combinado separadamente pelo cliente.

## MedicationRequestItemFormSet

| Campo | Tipo | Regra |
|---|---|---|
| `drug` | ModelChoice | `Drug.active=True`; label legível com nome/apresentação/código |
| `dose` | Decimal | obrigatório e > 0 |
| `dose_unit` | string | obrigatória |
| `route` | string | obrigatória |
| `frequency` | string | obrigatória; texto normalizado, nunca executado |
| `duration_value` | Decimal opcional | > 0 quando informado |
| `duration_unit` | string opcional | obrigatória quando `duration_value` existir |
| `instructions` | textarea opcional | máximo 2000; texto clínico excluído de logs/eventos |

A ordem é atribuída server-side pela posição do formset. O service repete os gates de DRAFT, autoria, escopo PEP, medicamento ativo, duplicidade e `RX_MAX_ITEMS_PER_REQUEST`.

## MedicationRequestSubmitForm

`confirm: boolean obrigatório`.

Antes de `DRAFT -> SUBMITTED`, o service revalida encontro aberto, autoria, permissão e existência de ao menos um item; congela a edição comum e agenda `prescription.created` somente após commit. A revisão farmacêutica ocorre na etapa de validação, não na submissão.

## MedicationRequestValidateForm

| Campo | Tipo | Regra |
|---|---|---|
| `manual_allergy_review_confirmed` | boolean condicional | necessário enquanto a fonte estruturada de alergias permanecer indisponível |
| `confirm_validation` | boolean | obrigatório |

Permissão: `prescription.validate_medication_request` + escopo PEP.

O POST recalcula o safety engine usando apenas `Interaction`/`DoseRule` ativos, aprovados e versionados. Achado `blocking=True` mantém a prescrição `SUBMITTED`. Fato de peso ausente ou regra não avaliável produz `NOT_EVALUABLE`, sem estimativa. A tentativa de revisão é preservada em `MedicationSafetyReview`/`MedicationSafetyFinding` append-only. O formulário não implementa assinatura jurídica/ICP-Brasil.

## MedicationRequestCancelForm

| Campo | Tipo | Regra |
|---|---|---|
| `reason` | textarea curta | obrigatória, normalizada, máximo 255 |
| `confirm` | boolean | obrigatório |

Cancelar não apaga histórico nem reverte estoque implicitamente. Qualquer devolução/estorno exige fluxo próprio futuro.

## MedicationDispenseHeaderForm

| Campo | Tipo | Regra |
|---|---|---|
| `operation_key` | UUID hidden | obrigatório; gerado no GET e usado para idempotência |
| `confirm` | boolean | obrigatório |

## MedicationDispenseItemFormSet

| Campo | Tipo | Regra |
|---|---|---|
| `request_item` | ModelChoice | item da prescrição alvo; label mostra medicamento/dose/via/frequência |
| `lot` | ModelChoice | lotes ativos com saldo; label mostra lote, validade e saldo |
| `quantity` | Decimal | > 0 |

A interface filtra escolhas úteis, mas o service é a fonte de verdade e, dentro de `transaction.atomic()` + `select_for_update()`, revalida: status `VALIDATED`, autorização, medicamento ativo, correspondência lote/Drug, lote/estoque ativos, validade, saldo acumulado e `operation_key`. Retry idêntico não consome saldo novamente; reutilização conflitante da chave é recusada.

## DrugForm

| Campo | Regra |
|---|---|
| `code` | obrigatório, normalizado, único |
| `name` | obrigatório |
| `presentation` | obrigatório |
| `strength_text` | opcional |
| `route_hint` | opcional e somente informativo |
| `dispense_unit` | obrigatório |
| `active` | boolean |

Permissão: `prescription.manage_drug_catalog`. Desativar é preferível a apagar; dados usados clinicamente não devem ser reescritos silenciosamente.

## Interaction / DoseRule

Não há formulário clínico público para conteúdo real nesta entrega. Referências começam inativas e só entram no safety engine quando têm fonte, versão, aprovador, data de aprovação e `active=True`. T-RX-02 continua como gate externo de governança. Nenhuma fórmula executável/`eval` é aceita.

## Estoque

Ajustes de estoque continuam por services explícitos e `StockMovement` append-only; não há formulário público genérico de edição direta de saldo.

## Mensagens de erro

Erros são pt-BR e não revelam SQL/constraint, existência de paciente fora do escopo, CPF/nome em erro técnico nem texto de alergia/instrução em logs.
