# Data Model — Spec 003 Prescrição e Farmácia

## Princípios

- UUID em novas entidades clínicas/farmacêuticas.
- `Patient` e `Encounter` continuam pertencendo ao PEP.
- conteúdo clínico concluído e movimentos de estoque são preservados; correções são novas entradas/transições, não edição destrutiva.
- FKs históricas usam `PROTECT` sempre que a exclusão quebraria rastreabilidade.
- quantidades monetárias não pertencem a esta spec; quantidades farmacêuticas usam `DecimalField` com unidade explícita.
- texto clínico livre é excluído do payload genérico do auditlog.

## Drug

Catálogo interno do medicamento.

Campos previstos:

```text
id: UUID PK
code: string unique
name: string
presentation: string
strength_text: string optional
route_hint: string optional
Dispense_unit: string
active: bool
created_at
updated_at
```

Invariantes:

- `code` normalizado e único;
- item inativo não aparece em novas prescrições/dispensações, mas relações históricas permanecem válidas;
- exclusão física não é exposta na UI depois de referenciado.

> Nomes/apresentações são dados de catálogo farmacêutico, não dados do paciente. Ainda assim, alterações são auditadas por governança.

## Interaction

Relação de segurança entre dois `Drug`.

```text
id: UUID PK
drug_a: FK Drug PROTECT
drug_b: FK Drug PROTECT
severity: INFO | MINOR | MODERATE | MAJOR | CONTRAINDICATED
blocking: bool
summary: text
reference_source: string
reference_version: string
approved_by: FK User PROTECT
approved_at: datetime
active: bool
created_at
updated_at
```

Constraints:

- `drug_a != drug_b`;
- par canônico único por versão (`min(drug_a, drug_b)`, `max(...)`, `reference_version`) implementado por normalização de service/model antes de persistir;
- registro sem `reference_source`, `reference_version`, `approved_by` e `approved_at` não pode ficar `active=True`;
- `blocking` é dado governado, não calculado por severidade no código.

## DoseRule

Regra estruturada de referência associada a um `Drug`. A existência do modelo não autoriza carregar regras clínicas sem fonte aprovada.

```text
id: UUID PK
drug: FK Drug PROTECT
rule_code: string
basis: AGE | WEIGHT | AGE_AND_WEIGHT
min_age_days: int optional
max_age_days: int optional
min_weight_kg: decimal optional
max_weight_kg: decimal optional
min_dose: decimal optional
max_dose: decimal optional
dose_unit: string
per_kg: bool
reference_source: string
reference_version: string
approved_by: FK User PROTECT
approved_at: datetime
active: bool
created_at
updated_at
```

Invariantes:

- intervalos mínimos não podem exceder máximos;
- regra com `basis` envolvendo peso requer parâmetros coerentes com peso e só pode ser avaliada quando houver fato clínico de peso aprovado;
- `per_kg=True` nunca usa peso digitado ad hoc na prescrição;
- regra ativa exige procedência e aprovação;
- fórmulas complexas fora desses limites exigem nova revisão de spec, não `eval`, expressão arbitrária ou lógica escondida em texto.

## MedicationRequest

Cabeçalho da prescrição.

```text
id: UUID PK
encounter: FK PEP.Encounter PROTECT
authored_by: FK User PROTECT
status: DRAFT | SUBMITTED | VALIDATED | CANCELLED
replaces: FK self PROTECT optional
submitted_at: datetime optional
validated_by: FK User PROTECT optional
validated_at: datetime optional
cancelled_by: FK User PROTECT optional
cancelled_at: datetime optional
cancellation_reason: string optional
created_at
updated_at
```

Invariantes:

- `Encounter` deve estar aberto para criar/submeter;
- autor deve possuir capacidade de prescrever + escopo PEP;
- `VALIDATED` exige `validated_by/validated_at`;
- `CANCELLED` exige ator, horário e motivo;
- `replaces`, quando presente, deve apontar para prescrição do mesmo encontro;
- após `SUBMITTED`, campos clínicos do cabeçalho/itens não são editados pela UI; correção gera nova prescrição com `replaces`.

Mudança de `status` só ocorre por service explícito, não por ModelForm genérico.

## MedicationRequestItem

```text
id: UUID PK
medication_request: FK MedicationRequest PROTECT
drug: FK Drug PROTECT
dose: decimal
dose_unit: string
route: string
frequency: string
duration_value: decimal optional
duration_unit: string optional
instructions: text optional
sequence: positive int
created_at
```

Invariantes:

- dose > 0;
- `drug.active=True` no momento de criação;
- sequência única dentro da prescrição;
- itens só podem ser adicionados/removidos enquanto a prescrição está `DRAFT`;
- `instructions` é texto clínico e deve ser excluído do auditlog genérico/eventos.

## MedicationSafetyReview

Snapshot técnico da revisão feita na validação farmacêutica.

```text
id: UUID PK
medication_request: FK MedicationRequest PROTECT
reviewed_by: FK User PROTECT
allergy_status: UNAVAILABLE | REVIEW_REQUIRED | REVIEW_CONFIRMED | STRUCTURED_CHECKED
dose_status: PASS | BLOCKED | NOT_EVALUABLE
blocking_findings: int
warning_findings: int
reference_version: string
created_at
```

Regras:

- é append-only;
- `UNAVAILABLE` nunca é convertido semanticamente em “sem alergias”;
- `reference_version` identifica o conjunto de referências usado na revisão;
- validação só pode usar uma revisão produzida no mesmo estado de itens da prescrição.

## MedicationSafetyFinding

Referência técnica aos achados da revisão, sem copiar texto de paciente.

```text
id: UUID PK
review: FK MedicationSafetyReview PROTECT
kind: INTERACTION | ALLERGY | DOSE
request_item: FK MedicationRequestItem PROTECT optional
interaction: FK Interaction PROTECT optional
dose_rule: FK DoseRule PROTECT optional
severity: string
blocking: bool
created_at
```

Para alergias futuras, um FK/identificador técnico ao registro PEP poderá ser adicionado por migration aprovada; esta spec não cria cadastro paralelo de alergia.

## StockItem

Agregado de estoque farmacêutico por medicamento e localização lógica inicial.

```text
id: UUID PK
drug: FK Drug PROTECT
storage_location: string
minimum_level: decimal >= 0
active: bool
created_at
updated_at
```

Constraint única inicial: `(drug, storage_location)`.

`storage_location` é deliberadamente simples nesta fase. A Spec 009 poderá migrar/integrar localização de estoque por contrato próprio sem apagar histórico farmacêutico.

## Lot

```text
id: UUID PK
stock_item: FK StockItem PROTECT
lot_number: string
expires_on: date
quantity_available: decimal >= 0
active: bool
created_at
updated_at
```

Constraints:

- `(stock_item, lot_number)` único;
- `quantity_available >= 0` por `CheckConstraint`;
- lote expirado na data da dispensação não é elegível;
- lote inativo não é elegível.

## MedicationDispense

Cabeçalho idempotente de dispensação.

```text
id: UUID PK
medication_request: FK MedicationRequest PROTECT
dispensed_by: FK User PROTECT
operation_key: UUID unique
dispensed_at: datetime
created_at
```

Invariantes:

- prescrição precisa estar `VALIDATED`;
- ator precisa de capacidade de dispensar + escopo PEP;
- mesma `operation_key` retorna/reconhece a operação já confirmada e não duplica consumo.

## MedicationDispenseItem

```text
id: UUID PK
dispense: FK MedicationDispense PROTECT
request_item: FK MedicationRequestItem PROTECT
lot: FK Lot PROTECT
quantity: decimal > 0
created_at
```

Invariantes:

- `lot.stock_item.drug == request_item.drug`;
- quantidade não pode exceder saldo disponível bloqueado na transação;
- lote deve estar ativo e não expirado;
- consumo acumulado de um item não pode exceder a quantidade dispensável definida pelo contrato do item; política de fracionamento específica deve ser aprovada antes de regras adicionais.

## StockMovement

Razão append-only de qualquer mudança de saldo farmacêutico.

```text
id: UUID PK
lot: FK Lot PROTECT
movement_type: DISPENSE | RECEIPT | ADJUSTMENT
quantity_delta: decimal non-zero
dispense_item: FK MedicationDispenseItem PROTECT optional
actor: FK User PROTECT
operation_key: UUID
reason: string optional
created_at
```

Regras:

- `DISPENSE` possui delta negativo e referencia `dispense_item`;
- movimentos são append-only;
- ajustes manuais exigem permissão específica e justificativa;
- recebimento comercial completo/fornecedor pertence à Spec 009; `RECEIPT` nesta fase representa apenas entrada farmacêutica autorizada, se habilitada por tarefa própria;
- `reason` é excluído do auditlog genérico quando puder conter informação sensível.

## Índices esperados

- `MedicationRequest(encounter, created_at)`;
- `MedicationRequest(status, created_at)`;
- `MedicationRequest(authored_by, created_at)`;
- `MedicationRequestItem(medication_request, sequence)`;
- `Interaction(drug_a, drug_b, active)`;
- `DoseRule(drug, active)`;
- `Lot(stock_item, expires_on, active)`;
- `MedicationDispense(medication_request, dispensed_at)`;
- `StockMovement(lot, created_at)`.

## Retenção e exclusão

- prescrição submetida/validada/cancelada: retenção clínica; sem delete pela UI;
- dispensação e movimentos: retenção clínica/operacional; sem delete pela UI;
- catálogo/referências: desativação lógica, preservando versões usadas;
- prazos jurídicos definitivos permanecem sob Spec 013; até lá não há purge automático de dados clínicos desta spec.

## Auditlog

Registrar modelos relevantes, excluindo pelo menos:

- `MedicationRequest.cancellation_reason` quando puder conter contexto clínico;
- `MedicationRequestItem.instructions`;
- texto de `Interaction.summary` em logs por objeto se não for necessário;
- `StockMovement.reason`.

Eventos e logs técnicos usam IDs, contagens, estado e timestamps; nunca copiam nome do paciente, CPF, instrução, alergia ou conteúdo clínico livre.
