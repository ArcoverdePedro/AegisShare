# Modelo de Dados — Spec 001 PEP

## Escopo desta iteração

Esta primeira implementação entrega o núcleo de identificação do paciente e a autorização por vínculo explícito. Encontros, evoluções, observações, condições, alergias e documentos clínicos permanecem nas tarefas seguintes da Spec 001.

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

## Retenção e LGPD

- dados clínicos e identificadores não devem ser apagados em cascata por exclusão de usuário; `created_by` usa `PROTECT`;
- exportação, anonimização, retenção definitiva e direitos do titular serão fechados na Spec 013;
- logs e notificações não devem reproduzir CPF, diagnóstico ou outros dados clínicos identificáveis.

## Rollback

A migration inicial do app `pep` é reversível por `migrate pep zero` enquanto não houver dependências posteriores. Em ambiente com dados reais, rollback destrutivo deve ser precedido por backup e janela de manutenção.