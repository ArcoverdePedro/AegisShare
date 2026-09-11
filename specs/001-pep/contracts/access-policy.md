# Política de Acesso — Spec 001 PEP

## Matriz inicial RBAC + ABAC

| Papel atual | Listar pacientes | Cadastrar | Abrir prontuário | Regra adicional |
|---|---:|---:|---:|---|
| `ADM` / superuser | sim | sim | sim | acesso administrativo global |
| `FUNC` | sim, apenas escopo acessível | sim | sim, se houver vínculo | criador do cadastro ou `PatientAccessGrant` ativo |
| `CLI` | não | não | não | deny-by-default |
| não autenticado | não | não | não | redirecionamento para login |

## Regras ABAC

1. O acesso individual ao paciente exige pelo menos uma condição verdadeira: usuário administrador, usuário criador do cadastro ou grant explícito ainda não expirado.
2. A listagem aplica a mesma política no queryset; não basta ocultar itens no template.
3. Tentativas de abrir paciente fora do escopo retornam `404`, evitando confirmar a existência do registro.
4. O cadastro cria grant automático para o profissional que realizou o cadastro, com justificativa `Cadastro inicial`.
5. Grants futuros devem registrar concedente, justificativa e expiração opcional.

## Evolução futura

O `CustomUser` atual possui apenas `ADM`, `FUNC` e `CLI`. Papéis clínicos finos (médico, enfermagem, farmácia etc.) serão introduzidos de forma compatível em tarefa própria do Core/PEP. Até lá, `FUNC` representa profissional interno e o vínculo por objeto limita o acesso clínico.