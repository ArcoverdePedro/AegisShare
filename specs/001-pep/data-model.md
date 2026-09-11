# Modelo de Dados — Spec 001 PEP

## Escopo desta iteração

O núcleo de identificação do paciente, autorização por vínculo explícito e encontros clínicos está implementado. Evoluções, observações, condições, alergias e documentos clínicos permanecem nas tarefas seguintes da Spec 001.

## Patient

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | chave primária, imutável |
| `identifier_type` | enum | `CPF` ou `OTHER` |
| `identifier` | string(64) | obrigatório; normalizado; único em conjunto com o tipo |
| `full_name` | string(255) | obrigatório |
| `birth_date` | date | obrigatório; não pode estar no futuro |
| `sex` | enum | `F`, `M`, `I`, `O`, `U` |
| `phone` | string(32) | opcional |
| `email` | email | opcional |
| `active` | bool | padrão `True` |
| `created_by` | FK User | `PROTECT`; profissional responsável pelo cadastro |
| `created_at` | datetime | automático |
| `updated_at` | datetime | automático |

### Constraints

- `UniqueConstraint(identifier_type, identifier)` impede duplicidade do identificador principal.
- CPF, quando usado, é persistido apenas com dígitos e validado por dígitos verificadores.
- Data de nascimento futura é inválida.
- Registros não são removidos fisicamente no fluxo normal; `active=False` será usado para inativação futura.

## PatientAccessGrant

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | chave primária |
| `patient` | FK Patient | cascade |
| `user` | FK User | cascade |
| `reason` | string(255) | justificativa do vínculo |
| `granted_by` | FK User | `PROTECT` |
| `expires_at` | datetime | opcional |
| `created_at` | datetime | automático |

### Constraints

- apenas um grant por par `patient/user`;
- grant expirado não autoriza acesso;
- administrador possui acesso global;
- usuário `FUNC` precisa de grant ativo ou ter criado o paciente;
- usuário `CLI` não acessa o PEP;
- criação de paciente é restrita a `ADM`/`FUNC`.

## Encounter

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | chave primária, imutável |
| `patient` | FK Patient | `PROTECT`; encontro não existe sem prontuário |
| `encounter_type` | enum | `CONSULTATION`, `EMERGENCY`, `INPATIENT`, `TELEHEALTH`, `OTHER` |
| `status` | enum | `OPEN`, `CLOSED`, `CANCELLED`; criação inicia em `OPEN` |
| `started_at` | datetime | início assistencial |
| `ended_at` | datetime | obrigatório quando `status=CLOSED` |
| `location` | string(160) | opcional |
| `reason` | text | opcional; conteúdo clínico não é replicado no auditlog |
| `responsible_professional` | FK User | `PROTECT`; profissional responsável pelo encontro |
| `created_by` | FK User | `PROTECT`; ator que abriu o encontro |
| `created_at` | datetime | automático |
| `updated_at` | datetime | automático |

### Regras do encontro

- apenas usuário interno com acesso atual ao paciente pode iniciar ou consultar o encontro;
- usuário fora do escopo recebe resposta sem revelar o conteúdo do encontro;
- horário de encerramento não pode ser anterior ao início;
- encontro `CLOSED` exige `ended_at`;
- encontro `OPEN` não possui `ended_at`;
- paciente, criador e profissional responsável usam `PROTECT` para preservar rastreabilidade;
- índices cobrem histórico por paciente/data, status e profissional/data.

## Retenção e LGPD

- dados clínicos e identificadores não devem ser apagados em cascata por exclusão de usuário;
- encontros preservam vínculo com paciente e profissionais usando `PROTECT`;
- exportação, anonimização, retenção definitiva e direitos do titular serão fechados na Spec 013;
- logs e notificações não devem reproduzir CPF, diagnóstico, motivo do atendimento ou outros dados clínicos identificáveis.

## Rollback

A migration `pep.0002_encounter` é reversível enquanto nenhuma migration posterior depender da tabela de encontros. Em ambiente com dados reais, qualquer rollback destrutivo deve ser precedido por backup, validação de dependências e janela de manutenção.
