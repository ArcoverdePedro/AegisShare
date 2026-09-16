# Modelo de dados — Spec 012 v1 (v1 aprovada)

`Patient` continua canônico em `apps.clinical.pep`; não sofre alteração.

## PatientExportReceipt

| Campo | Tipo/regra |
|---|---|
| id | UUID, PK gerada pelo servidor |
| patient | FK Patient, PROTECT |
| created_by | FK AUTH_USER_MODEL, PROTECT |
| created_at | timestamp do servidor, timezone-aware |
| contract_version | valor fixo `patient-r4-v1` |
| content_sha256 | 64 caracteres hexadecimais; hash dos bytes exatos entregues |

Permissão customizada: `export_patient` no app `interoperability`. Permissões CRUD padrão não concedem exportação.

Registro append-only: sem edição/exclusão pela UI/admin, `save()` de instância persistida e `delete()` rejeitados seguindo o padrão clínico existente. Não prometer imutabilidade contra superusuário do banco ou `QuerySet.update()`: permissões operacionais do banco continuam necessárias. Sem expurgo até política de retenção aprovada.

Auditlog registra metadados técnicos do recibo, nunca payload exportado. Reusar auditoria ACCESS do Patient sem copiar nome/data de nascimento. Não criar índice extra sem consulta concreta; PK e FKs bastam na v1.
