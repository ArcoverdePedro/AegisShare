# Modelo de Dados — Spec 002 ADT

## Princípio de ownership

`Patient` e `Encounter` permanecem canônicos no módulo PEP. O ADT não duplica essas entidades; referencia seus UUIDs por relações Django protegidas.

## Location

Representa unidade, setor, ala, quarto ou outro agrupador operacional.

Campos implementados:

- `id: UUID PK`;
- `code: CharField` único;
- `name: CharField`;
- `kind: UNIT|WARD|ROOM|OTHER`;
- `parent: FK self nullable PROTECT`;
- `active: bool`;
- timestamps.

Regras: código normalizado e não vazio, hierarquia não referencia a si própria e desativação não apaga histórico.

## UserLocationAccess

Escopo operacional explícito usuário↔local para RBAC + ABAC ADT.

- `id: UUID PK`;
- `user: FK User`;
- `location: FK Location`;
- `granted_by: FK User nullable`;
- `created_at`;
- `UniqueConstraint(user, location)`.

`FUNC` sem associação explícita não herda acesso a um local.

## Bed

Representa o recurso físico/lógico ocupável.

- `id: UUID PK`;
- `location: FK Location PROTECT`;
- `code`, `label`;
- `operational_status: AVAILABLE|BLOCKED|OUT_OF_SERVICE`;
- `active` e timestamps;
- `UniqueConstraint(location, code)`.

`OCCUPIED` é derivado da existência de `BedOccupancy` ativa; não é duplicado em `operational_status`.

## Admission

Início administrativo da internação vinculada a um `Encounter` PEP.

- `id: UUID PK`;
- `encounter: OneToOneField(pep.Encounter, PROTECT)`;
- `admitted_at`;
- `admitted_by: FK User PROTECT`;
- `operation_key: UUID unique`;
- `created_at`.

Regras: encontro `INPATIENT`, aberto, `admitted_at >= Encounter.started_at` e uma admissão por encontro. O serviço usa chave de operação para idempotência e bloqueio transacional.

## BedOccupancy

Intervalo de ocupação de um leito por uma admissão.

- `id: UUID PK`;
- `admission: FK Admission PROTECT`;
- `bed: FK Bed PROTECT`;
- `started_at`, `ended_at nullable`;
- `started_by`, `ended_by nullable`;
- `end_reason: TRANSFER|DISCHARGE|CORRECTION`;
- `created_at`.

Constraints/regras:

- `ended_at >= started_at`;
- uma ocupação ativa (`ended_at IS NULL`) por `bed`;
- uma ocupação ativa por `admission`;
- constraints parciais PostgreSQL constituem a última barreira contra dupla ocupação;
- encerramento exige `ended_by` e `end_reason`.

## Transfer

Registro append-only do movimento entre ocupações.

Campos implementados:

- `id: UUID PK`;
- `admission: FK Admission PROTECT`;
- `source_occupancy: OneToOneField BedOccupancy PROTECT`;
- `destination_occupancy: OneToOneField BedOccupancy PROTECT`;
- `transferred_at`;
- `transferred_by: FK User PROTECT`;
- `reason: CharField(255)` opcional e sensível;
- `operation_key: UUID unique`;
- `created_at`.

Regras:

- origem e destino pertencem à mesma admissão;
- leitos são diferentes;
- `source_occupancy.ended_at == transferred_at` e `destination_occupancy.started_at == transferred_at` no serviço;
- a criação ocorre junto do encerramento da origem e abertura do destino em `transaction.atomic()`;
- `reason` é excluído do auditlog serializado;
- registro persistido não pode ser editado/excluído pelo modelo.

## Discharge

Encerramento administrativo da internação.

Campos implementados:

- `id: UUID PK`;
- `admission: OneToOneField Admission PROTECT`;
- `final_occupancy: OneToOneField BedOccupancy PROTECT`;
- `discharged_at`;
- `disposition: HOME|TRANSFER_EXTERNAL|DEATH|OTHER`;
- `reason: CharField(255)` opcional e sensível;
- `discharged_by: FK User PROTECT`;
- `operation_key: UUID unique`;
- `created_at`.

Regras:

- uma alta por admissão;
- encerra a ocupação ativa no mesmo timestamp;
- fecha o `Encounter` PEP no mesmo bloco transacional e atribui `Encounter.ended_at = discharged_at`;
- `reason` é excluído do auditlog serializado;
- alta persistida não pode ser editada/excluída pelo modelo.

## Relações

```text
Patient (PEP)
  └── Encounter (PEP, INPATIENT)
        └── Admission (ADT)
              ├── BedOccupancy 1..N ──> Bed ──> Location
              ├── Transfer 0..N
              └── Discharge 0..1

User ──> UserLocationAccess ──> Location
```

## Auditoria e dados sensíveis

- `Location.code/name` e `Bed.code/label` são operacionais, porém sua combinação com ocupação pode revelar localização do paciente;
- `reason` de transferência/alta não entra em payload amplo de auditlog e não deverá entrar em eventos WebSocket/logs técnicos;
- leituras identificáveis ainda dependem da entrega T-ADT-09 para auditoria explícita de acesso;
- retenção jurídica definitiva pertence à Spec 013; esta spec proíbe exclusão automática de histórico ADT.

## Rollback

As migrations ADT criam tabelas próprias e relações para o PEP sem mover ou renomear `Encounter`. `0003_transfer_discharge` é estruturalmente reversível enquanto não houver dependências posteriores; em ambiente com dados reais, rollback operacional deve preferir reversão de código/feature flag e preservar tabelas históricas.
