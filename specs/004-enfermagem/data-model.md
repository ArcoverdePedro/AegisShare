# Data Model — Spec 004 Enfermagem

## Princípios

- UUID em novas entidades clínicas.
- `Patient` e `Encounter` continuam pertencendo ao PEP.
- medicamento, item prescrito, dispensação e lote continuam pertencendo à Spec 003.
- registros clínicos confirmados são append-only pela interface comum.
- correção cria novo registro; não reescreve o fato anterior.
- FKs históricas usam `PROTECT` quando exclusão quebraria rastreabilidade.
- dados numéricos usam `DecimalField`/inteiro com unidade definida pelo próprio campo; não existe conversão clínica implícita.
- texto livre não faz parte deste recorte inicial.

## VitalSignsRecord

Snapshot estruturado de uma aferição de enfermagem.

```text
id: UUID PK
encounter: FK PEP.Encounter PROTECT
recorded_by: FK User PROTECT
recorded_at: datetime
idempotency_key: UUID unique
replaces: FK self PROTECT optional
origin: ONLINE | OFFLINE_SYNC

temperature_c: decimal optional
heart_rate_bpm: positive int optional
respiratory_rate_irpm: positive int optional
systolic_bp_mmhg: positive int optional
diastolic_bp_mmhg: positive int optional
oxygen_saturation_pct: decimal optional
weight_kg: decimal optional

created_at
```

### Invariantes

- pelo menos uma medida deve estar presente;
- todos os valores informados devem ser numericamente positivos quando a própria grandeza não admitir zero no contrato técnico;
- `oxygen_saturation_pct`, quando presente, deve caber no domínio representacional percentual `0 < valor <= 100`; isso é integridade matemática, não interpretação clínica;
- pressão sistólica e diastólica podem existir juntas como par; a política de obrigatoriedade conjunta deve ser validada na implementação do formulário sem inferir diagnóstico;
- `recorded_at` não pode estar no futuro além de tolerância técnica mínima definida por configuração/teste; nenhuma janela clínica é inventada;
- `replaces`, quando presente, aponta para registro do mesmo `Encounter`;
- um registro substituído não é alterado nem apagado;
- mesma `idempotency_key` não cria segundo registro;
- `origin` é metadado técnico e não altera semântica clínica do fato;
- `OFFLINE_SYNC` somente pode ser criado pela rotina de sincronização autorizada.

### Peso

`weight_kg` é armazenado como fato estruturado em quilogramas, com `recorded_at`, autor e encontro. Isso permite proveniência, mas não define sozinho elegibilidade para decisão medicamentosa.

Selector futuro proposto:

```text
latest_weight_fact(encounter|patient) -> {
  weight_kg,
  recorded_at,
  record_id,
  recorded_by_id,
  encounter_id
}
```

O selector deve devolver o fato e sua proveniência; **não deve aplicar uma janela de validade inventada pelo código**. A política de atualidade/origem é gate de governança clínica/farmacêutica antes da integração automática com RX.

## MedicationAdministration

Registro de administração efetivamente confirmada.

```text
id: UUID PK
dispense_item: FK prescription.MedicationDispenseItem PROTECT
administered_by: FK User PROTECT
administered_at: datetime
administered_dose: decimal
administered_dose_unit: string
operation_key: UUID unique
created_at
```

O encontro, paciente, item prescrito, medicamento e lote são alcançados pela cadeia:

```text
MedicationAdministration
  -> MedicationDispenseItem
  -> MedicationDispense
  -> MedicationRequest
  -> Encounter
```

E o lote pela cadeia:

```text
MedicationAdministration
  -> MedicationDispenseItem
  -> Lot
```

### Invariantes

- `dispense_item` deve pertencer a prescrição validada/dispensação confirmada da Spec 003;
- ator precisa possuir capacidade de administrar + escopo PEP válido no momento da confirmação;
- `administered_dose > 0`;
- unidade é explícita e não sofre conversão automática;
- `operation_key` é única e torna retry idempotente;
- registro confirmado não é editável/excluível pela UI comum;
- administração não pode ser criada por fila offline nesta versão;
- a v1 registra somente administração efetiva. Recusa, omissão, atraso, erro, substituição, administração parcial e demais exceções exigem contrato clínico posterior e não são codificados como enums especulativos agora.

## Constraints esperadas

### VitalSignsRecord

- `UniqueConstraint(idempotency_key)`;
- `CheckConstraint` para pelo menos uma medida preenchida, se a expressão permanecer legível/manutenível; caso contrário validar no form/service e cobrir por testes, sem constraint gigante só por arquitetura;
- checks simples de positividade/domínio percentual quando adequados ao PostgreSQL.

### MedicationAdministration

- `UniqueConstraint(operation_key)`;
- `CheckConstraint(administered_dose__gt=0)`.

Uma constraint de “um dispense item só pode ser administrado uma vez” **não é definida nesta spec**, pois dispensações/administrações fracionadas podem existir em fluxos reais e a política correspondente não deve ser inventada.

## Índices esperados

- `VitalSignsRecord(encounter, recorded_at)`;
- `VitalSignsRecord(recorded_by, recorded_at)`;
- `MedicationAdministration(dispense_item, administered_at)`;
- `MedicationAdministration(administered_by, administered_at)`.

## Retenção e exclusão

- sinais vitais persistidos: retenção clínica; sem delete pela UI;
- administração concluída: retenção clínica; sem delete pela UI;
- correção: novo registro com referência ao anterior;
- prazos jurídicos definitivos permanecem sob a spec de governança/retenção correspondente; até lá não há purge automático desses registros.

## Auditlog

Os modelos podem ser registrados no `django-auditlog`, mas logs técnicos/eventos genéricos devem preferir IDs e metadados. Valores clínicos não devem ser duplicados desnecessariamente em logs de aplicação.

Leitura identificável é auditada pelo mesmo padrão do PEP, fora do simples histórico automático de alteração.