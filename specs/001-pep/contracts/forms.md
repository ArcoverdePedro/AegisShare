# Contrato de Formulários — Spec 001 PEP

| Formulário | Campos principais | Validações | Permissão |
|---|---|---|---|
| `PatientForm` | nome, CPF/identificador, data de nascimento, sexo, contatos mínimos | identificador válido, DN <= hoje, duplicidade sinalizada | `ADM`/`FUNC` |
| `EncounterForm` | tipo, início, setor/local, motivo | paciente acessível, datas coerentes, encontro novo inicia aberto | profissional interno autorizado |
| `ClinicalEvolutionForm` | conteúdo | encontro acessível e `OPEN`, conteúdo obrigatório, autor autenticado; registro é append-only | profissional interno autorizado |
| `ClinicalEvolutionAmendmentForm` | motivo do adendo, conteúdo | evolução original acessível, mesmo encontro, motivo obrigatório, novo registro append-only | profissional interno autorizado |
| `ObservationForm` | encontro, código/tipo, valor, unidade, data/hora | futuro: tipo/unidade coerentes, horário válido, acesso ao encontro | futuro |
| `ConditionForm` | paciente/encontro, descrição/código, status | futuro: paciente acessível, status permitido | futuro |
| `AllergyForm` | substância, reação, gravidade, status | futuro: substância obrigatória, gravidade/status válidos | futuro |
| `ClinicalDocumentSignForm` | confirmação, segundo fator quando exigido | futuro: conteúdo não alterado, signatário autorizado, assinatura ainda pendente | futuro T-PEP-08 |

## Imutabilidade

- `ClinicalEvolutionForm` cria um registro novo; não existe formulário de edição.
- Correções usam `ClinicalEvolutionAmendmentForm`, que cria outra `ClinicalEvolution` vinculada por `amendment_of`.
- O registro original permanece intacto e não pode ser excluído pelo fluxo de domínio.
- O conteúdo e o motivo do adendo não são replicados no payload do `django-auditlog`.

## Mensagens e segurança

Erros de validação devem ser específicos para o usuário autorizado, mas respostas a usuários sem acesso não devem revelar a existência ou conteúdo de dados clínicos.
