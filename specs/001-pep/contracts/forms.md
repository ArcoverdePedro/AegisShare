# Contrato de Formulários — Spec 001 PEP

| Formulário | Campos principais | Validações | Permissão |
|---|---|---|---|
| `PatientForm` | nome, CPF/identificador, data de nascimento, sexo, contatos mínimos | identificador válido, DN <= hoje, duplicidade sinalizada | staff/médico autorizado |
| `EncounterForm` | paciente, tipo, início, setor/local | paciente acessível, datas coerentes, contexto assistencial válido | profissional autorizado |
| `ClinicalEvolutionForm` | encontro, conteúdo, tipo de evolução | encontro acessível/aberto, conteúdo obrigatório, tamanho máximo, autor autenticado | papel clínico autorizado |
| `ObservationForm` | encontro, código/tipo, valor, unidade, data/hora | tipo/unidade coerentes, horário válido, acesso ao encontro | papel clínico autorizado |
| `ConditionForm` | paciente/encontro, descrição/código, status | paciente acessível, status permitido | papel clínico autorizado |
| `AllergyForm` | substância, reação, gravidade, status | substância obrigatória, gravidade/status válidos | papel clínico autorizado |
| `ClinicalDocumentSignForm` | confirmação, segundo fator quando exigido | conteúdo não alterado, signatário autorizado, assinatura ainda pendente | signatário autorizado |

## Mensagens e segurança

Erros de validação devem ser específicos para o usuário autorizado, mas respostas a usuários sem acesso não devem revelar a existência ou conteúdo de dados clínicos.