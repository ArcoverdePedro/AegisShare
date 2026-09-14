# Contrato de Formulários — Spec 003 Prescrição e Farmácia

## MedicationRequestCreateForm

| Campo | Tipo | Regra |
|---|---|---|
| `encounter` | ModelChoice | somente encontros abertos de pacientes no escopo PEP do usuário |
| `replaces` | UUID/hidden opcional | somente prescrição do mesmo encontro e acessível |

Permissão: `prescription.prescribe_medication` + escopo PEP.

O paciente não é enviado como campo independente: é derivado do `Encounter`, evitando combinações inconsistentes paciente/encontro.

## MedicationRequestItemFormSet

| Campo | Tipo | Regra |
|---|---|---|
| `drug` | ModelChoice | `Drug.active=True` |
| `dose` | Decimal | obrigatório e > 0 |
| `dose_unit` | string/choice governada | obrigatória |
| `route` | string/choice governada | obrigatória |
| `frequency` | string | obrigatória; normalizada sem executar expressão |
| `duration_value` | Decimal opcional | > 0 quando informado |
| `duration_unit` | string opcional | obrigatório quando `duration_value` existir |
| `instructions` | textarea opcional | limite explícito; texto clínico, não copiar para logs/eventos |
| `sequence` | hidden/int | ordem única dentro da prescrição |

Regras do formset:

- pelo menos um item válido;
- limite máximo configurável de itens por submissão para evitar abuso;
- duplicidade do mesmo `Drug` gera aviso/erro conforme contrato clínico aprovado; não é silenciosamente agregada;
- edição/adicionamento/remoção só em `DRAFT`;
- validações são repetidas no service antes de persistir/submeter.

## MedicationRequestSubmitForm

Campos:

```text
confirm: boolean obrigatório
```

Permissão: `prescription.prescribe_medication`, autoria autorizada e escopo PEP.

Antes da transição `DRAFT -> SUBMITTED`, o service:

1. revalida encontro aberto;
2. confirma existência de item;
3. congela conteúdo clínico para edição comum;
4. produz revisão preliminar de segurança quando as referências estiverem disponíveis;
5. registra auditoria e agenda `prescription.created` após commit.

## MedicationRequestValidateForm

| Campo | Tipo | Regra |
|---|---|---|
| `manual_allergy_review_confirmed` | boolean condicional | obrigatório apenas quando a fonte estruturada de alergias estiver `UNAVAILABLE`/`REVIEW_REQUIRED` |
| `confirm_validation` | boolean | obrigatório |

Permissão: `prescription.validate_medication_request` + escopo PEP.

Regras:

- prescrição precisa estar `SUBMITTED`;
- safety review é recalculada/revalidada no servidor no momento do POST;
- achado configurado como `blocking=True` impede validação; esta primeira versão não oferece checkbox genérico de “ignorar interação”;
- regra de dose dependente de fato ausente produz `NOT_EVALUABLE`; a política institucional deve definir se isso bloqueia ou exige revisão específica antes de habilitar regras reais;
- ausência da fonte estruturada de alergia nunca vira checkbox pré-marcado ou mensagem “sem alergia”;
- validação registra `validated_by`/`validated_at` e um `MedicationSafetyReview` append-only;
- este formulário não implementa assinatura ICP-Brasil/assinatura jurídica.

## MedicationRequestCancelForm

| Campo | Tipo | Regra |
|---|---|---|
| `reason` | textarea curta | obrigatória, com limite explícito |
| `confirm` | boolean | obrigatório |

Permissão: política de cancelamento definida em `access-policy.md` + escopo PEP.

Regras:

- não apaga a prescrição;
- registra ator/horário/motivo e transiciona para `CANCELLED`;
- se já houver dispensação, cancelamento não reverte estoque automaticamente; qualquer devolução/estorno exige fluxo explícito futuro.

## MedicationDispenseForm

Campos de cabeçalho:

```text
operation_key: UUID hidden, obrigatório
confirm: boolean obrigatório
```

Itens são enviados por `MedicationDispenseItemFormSet`.

Permissão: `prescription.dispense_medication` + escopo PEP.

## MedicationDispenseItemFormSet

| Campo | Tipo | Regra |
|---|---|---|
| `request_item` | ModelChoice/hidden | item da prescrição validada alvo |
| `lot` | ModelChoice | lote do mesmo medicamento, ativo, não expirado e com saldo potencial |
| `quantity` | Decimal | > 0 |

Regras críticas repetidas em `transaction.atomic()`:

- prescrição ainda `VALIDATED`;
- lote corresponde ao `Drug` do item;
- lote não expirou;
- saldo bloqueado é suficiente;
- quantidade acumulada não ultrapassa o limite dispensável contratado;
- `operation_key` repetida não consome saldo novamente.

## DrugForm

| Campo | Regra |
|---|---|
| `code` | obrigatório, normalizado, único |
| `name` | obrigatório |
| `presentation` | obrigatório |
| `strength_text` | opcional |
| `route_hint` | opcional; informativo, não prescreve automaticamente |
| `dispense_unit` | obrigatório |
| `active` | boolean |

Permissão: `prescription.manage_drug_catalog`.

Desativar é preferível a excluir. Edição que mudaria significado clínico histórico deve criar versão/referência nova em vez de alterar registros passados silenciosamente.

## InteractionReferenceForm / DoseRuleReferenceForm

Inicialmente restritos a manutenção administrativa controlada. Antes de `active=True`, exigem:

- fonte da referência;
- versão;
- aprovador autorizado;
- data de aprovação;
- campos estruturados válidos.

Nunca aceitar código executável, expressão arbitrária ou `eval` como fórmula de dose.

## StockAdjustmentForm

Não possui rota pública na primeira superfície. Caso habilitado em tarefa própria:

```text
lot
quantity_delta
reason
operation_key
```

Permissão: `prescription.manage_pharmacy_stock`.

Ajuste é `StockMovement` append-only, nunca edição direta não auditada do saldo. O service deve bloquear resultado negativo.

## Mensagens de erro

Mensagens devem ser em pt-BR, úteis e sem revelar:

- SQL/constraint interna;
- existência de prescrição de paciente fora do escopo;
- nome/CPF em erro técnico;
- conteúdo de alergia/instrução clínica em logs.
