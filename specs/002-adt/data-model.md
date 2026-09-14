# Modelo de Dados — Spec 002 ADT

## Princípio de ownership

`Patient` e `Encounter` permanecem canônicos no módulo PEP. O ADT não duplica essas entidades; referencia seus UUIDs por `ForeignKey`.

## Location

Representa unidade, setor, ala, quarto ou outro agrupador operacional.

Campos previstos:

- `id: UUID PK`;
- `code: CharField` único por escopo organizacional;
- `name: CharField`;
- `kind: TextChoices` (`UNIT`, `WARD`, `ROOM`, `OTHER`);
- `parent: FK self nullable`;
- `active: bool`;
- timestamps.

Regras:

- código normalizado e não vazio;
- hierarquia não pode referenciar a si própria;
- desativação não apaga histórico.

## Bed

Representa o recurso físico/lógico ocupável.

Campos previstos:

- `id: UUID PK`;
- `location: FK Location PROTECT`;
- `code: CharField`;
- `label: CharField`;
- `operational_status: AVAILABLE|BLOCKED|OUT_OF_SERVICE`;
- `active: bool`;
- timestamps.

Constraints:

- `UniqueConstraint(location, code)`;
- índices por `location`, `operational_status`, `active`.

`OCCUPIED` não é gravado em `operational_status`; é derivado da existência de `BedOccupancy` ativa. Assim evitamos divergência entre um boolean/estado gravado e a ocupação real.

## Admission

Marca o início administrativo da internação vinculada a um `Encounter` PEP.

Campos previstos:

- `id: UUID PK`;
- `encounter: OneToOneField(pep.Encounter, PROTECT)`;
- `admitted_at: DateTimeField`;
- `admitted_by: FK User PROTECT`;
- `operation_key: UUID` único para idempotência;
- `created_at`.

Regras:

- `Encounter.encounter_type == INPATIENT`;
- `Encounter.status == OPEN`;
- `admitted_at >= Encounter.started_at` salvo ajuste administrativo explicitamente auditado no futuro;
- um encontro possui no máximo uma admissão ADT.

## BedOccupancy

Intervalo de ocupação de um leito por uma admissão.

Campos previstos:

- `id: UUID PK`;
- `admission: FK Admission PROTECT`;
- `bed: FK Bed PROTECT`;
- `started_at: DateTimeField`;
- `ended_at: DateTimeField nullable`;
- `started_by: FK User PROTECT`;
- `ended_by: FK User PROTECT nullable`;
- `end_reason: ADMISSION_TRANSFER|TRANSFER|DISCHARGE|CORRECTION`;
- timestamps.

Constraints/regras:

- `ended_at >= started_at`;
- somente uma ocupação ativa (`ended_at IS NULL`) por `bed`;
- somente uma ocupação ativa por `admission`;
- constraint condicional deve ser aplicada no PostgreSQL via `UniqueConstraint(..., condition=Q(ended_at__isnull=True))` se compatível com o schema final;
- registros concluídos não são editados/excluídos pela interface comum.

## Transfer

Registro append-only do movimento entre ocupações.

Campos previstos:

- `id: UUID PK`;
- `admission: FK Admission PROTECT`;
- `from_occupancy: OneToOneField BedOccupancy PROTECT`;
- `to_occupancy: OneToOneField BedOccupancy PROTECT`;
- `transferred_at: DateTimeField`;
- `reason: CharField` curto, tratado como dado sensível e excluído de payloads de evento/auditlog serializado;
- `performed_by: FK User PROTECT`;
- `operation_key: UUID unique`;
- `created_at`.

Regras:

- origem e destino pertencem à mesma admissão;
- leitos de origem/destino devem ser diferentes;
- `from_occupancy.ended_at == transferred_at` e `to_occupancy.started_at == transferred_at` na operação de serviço;
- não permitir alteração destrutiva após persistência.

## Discharge

Encerramento administrativo da internação.

Campos previstos:

- `id: UUID PK`;
- `admission: OneToOneField Admission PROTECT`;
- `discharged_at: DateTimeField`;
- `disposition: HOME|TRANSFER_EXTERNAL|DEATH|OTHER`;
- `reason: CharField/TextField` opcional e sensível;
- `performed_by: FK User PROTECT`;
- `operation_key: UUID unique`;
- `created_at`.

Regras:

- só existe para admissão sem alta anterior;
- encerra a ocupação ativa no mesmo timestamp;
- fecha o `Encounter` PEP no mesmo bloco transacional;
- `Encounter.ended_at` recebe `discharged_at`;
- uma alta concluída não é editada/excluída; correções futuras devem usar mecanismo de adendo/correção auditável definido por nova tarefa/spec.

## Relações

```text
Patient (PEP)
  └── Encounter (PEP, INPATIENT)
        └── Admission (ADT)
              ├── BedOccupancy 1..N ──> Bed ──> Location
              ├── Transfer 0..N
              └── Discharge 0..1
```

## Auditoria e dados sensíveis

- `Location.code/name` e `Bed.code/label` são dados operacionais, mas podem revelar localização do paciente quando combinados com ocupação;
- `reason` de admissão/transferência/alta não deve entrar em eventos WebSocket, logs técnicos ou serialização ampla de auditlog;
- leituras que exibam paciente identificável devem gerar `ACCESS` auditável;
- retenção jurídica definitiva é delegada à Spec 013; esta spec proíbe exclusão automática de histórico ADT.

## Rollback

As migrations iniciais criam somente tabelas ADT e relações para PEP. Nenhuma migration inicial renomeia ou move `Encounter`. Em ambientes com dados reais, rollback operacional deve reverter código/feature flag sem destruir tabelas históricas.
