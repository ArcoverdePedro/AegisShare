# Modelo de dados — Spec 013 v1 (v1 aprovada)

## DataSubjectRequest

| Campo | Tipo/regra |
|---|---|
| id | UUID, PK gerada pelo servidor e protocolo técnico |
| patient | FK `pep.Patient`, PROTECT |
| category | TextChoices: ACCESS, CORRECTION, DELETION, PORTABILITY, OTHER |
| summary | texto obrigatório, strip, máximo 2000 caracteres |
| status | TextChoices: RECEIVED, IN_REVIEW, CLOSED; inicial RECEIVED |
| created_by | FK AUTH_USER_MODEL, PROTECT |
| created_at | timestamp timezone-aware do servidor |

Índice composto `(status, created_at)` para fila filtrada; ordenação `-created_at, -id`. Paciente/autor usam índices das FKs.

Capacidades customizadas: `compliance.view_requests`, `compliance.register_request`, `compliance.process_request`. Capacidades nativas de CRUD não substituem essas regras. Nenhuma concessão automática a grupos.

Cadastro sem rota de edição/exclusão. Após criação, somente status pode mudar pelo fluxo transacional; resumo e categoria permanecem como recebidos. Correções administrativas adicionais/reabertura ficam para extensão aprovada.

## DataSubjectRequestEvent

| Campo | Tipo/regra |
|---|---|
| id | UUID, PK |
| request | FK DataSubjectRequest, PROTECT |
| from_status | vazio somente no evento inicial |
| to_status | RECEIVED, IN_REVIEW ou CLOSED |
| actor | FK AUTH_USER_MODEL, PROTECT |
| note | texto strip, máximo 2000; obrigatório no encerramento |
| created_at | timestamp timezone-aware do servidor |

`UniqueConstraint(request, to_status)` assegura um evento por estado na sequência v1. Evento inicial: vazio → RECEIVED; nota vazia, sem duplicar o resumo. Demais eventos seguem `contracts/transitions.md`.

Histórico ordenado por `created_at, id`, sem edição/exclusão pela aplicação; `save()` de registro persistido e `delete()` rejeitados conforme os modelos clínicos existentes. Não registrar models no admin editável.

## Minimização e auditoria

`__str__` usa somente tipo e UUID. Excluir `summary` e `note` dos diffs e da serialização auditável; não copiar paciente completo, CPF, nome ou nascimento. Histórico administrativo restrito é a fonte das notas, não o auditlog genérico.

Nenhuma coluna de documento de identidade, endereço, telefone, e-mail, anexos ou destino externo. Não adicionar `Consent`, `RetentionPolicy` ou `RiskAssessment` sem caso de uso e contratos próprios aprovados.
