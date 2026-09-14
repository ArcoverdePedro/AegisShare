# Política de Acesso — Spec 002 ADT

## Objetivo

Definir a matriz RBAC + ABAC do módulo ADT sem ampliar implicitamente os papéis atuais do AegisShare. O princípio é `deny-by-default`: autenticação por sessão é obrigatória e cada mutação exige capacidade ADT explícita, além do escopo clínico do PEP quando houver paciente identificável.

## Capacidades ADT

As capacidades abaixo devem ser implementadas como permissões Django (`auth_permission`) e atribuídas a grupos operacionais, evitando codificar autorização apenas em `nivel_permissao`:

| Capacidade | Permissão prevista | Uso |
|---|---|---|
| visualizar mapa operacional | `adt.view_bed_map` | consultar estado e disponibilidade de leitos |
| admitir paciente | `adt.admit_patient` | criar `Admission` e primeira ocupação |
| transferir internação | `adt.transfer_patient` | encerrar origem e ocupar destino |
| registrar alta | `adt.discharge_patient` | criar `Discharge`, liberar leito e fechar `Encounter` |
| gerir estado do leito | `adt.manage_bed_status` | bloquear, desbloquear ou retirar leito de serviço |
| consultar histórico ADT | `adt.view_movement_history` | reconstruir admissão, ocupações, transferências e alta |

Nenhuma permissão ADT é concedida automaticamente apenas porque o usuário é `FUNC`. Grupos e permissões são o RBAC fino; o vínculo com paciente/local é o ABAC.

## Matriz por papel atual

| Papel atual | Mapa | Admitir | Transferir | Alta | Gerir leito | Ver PHI do ocupante |
|---|---:|---:|---:|---:|---:|---:|
| `ADM` / superuser | sim | sim | sim | sim | sim | conforme política PEP; superuser mantém bypass administrativo auditável |
| `FUNC` | somente com permissão | somente com permissão | somente com permissão | somente com permissão | somente com permissão | somente com escopo PEP válido |
| `CLI` | não | não | não | não | não | não |
| não autenticado | não | não | não | não | não | não |

## Regras ABAC

1. Para qualquer operação que revele paciente identificável, o usuário deve passar também por `apps.clinical.pep.permissions` para o paciente/encontro correspondente.
2. A ausência de grant PEP não impede necessariamente a visualização do **estado operacional mínimo** de um leito quando o usuário possui `adt.view_bed_map`; nesse caso o servidor não renderiza nome, CPF, data de nascimento, diagnóstico, motivo clínico ou qualquer identificador indireto do ocupante.
3. Admitir exige: `adt.admit_patient`, encontro `INPATIENT` aberto, escopo PEP válido sobre o paciente e leito dentro do escopo/local permitido ao usuário.
4. Transferir exige: `adt.transfer_patient`, acesso PEP válido ao paciente/admissão, ocupação ativa atual e acesso ao local de destino.
5. Alta exige: `adt.discharge_patient`, acesso PEP válido e admissão ainda ativa. A autorização é revalidada dentro do serviço transacional antes de persistir a alta.
6. Gestão do estado físico do leito exige `adt.manage_bed_status` e não concede, por si só, direito de visualizar PHI do ocupante.
7. Histórico ADT identificável exige `adt.view_movement_history` **e** escopo PEP atual; sem esse escopo, a rota deve responder `404` quando a existência do paciente/admissão constituir exposição indevida.
8. Querysets de listas e mapa devem aplicar a política no servidor; esconder ações no template não é controle de acesso.
9. Toda mutação crítica revalida autorização e estado do objeto dentro de `transaction.atomic()` para evitar TOCTOU entre a tela e o `POST`.
10. Eventos WebSocket apenas invalidam/solicitam refresh; a autorização para o fragmento atualizado é reavaliada no servidor em cada leitura.

## Escopo organizacional/local

A primeira implementação não adicionará uma hierarquia organizacional paralela. O escopo local será representado pelas `Location` acessíveis ao usuário por regra configurável no serviço de permissão. Enquanto não existir modelo institucional dedicado:

- `ADM` pode operar globalmente;
- `FUNC` precisa da capacidade ADT e de associação explícita ao escopo/local disponibilizada pela configuração do módulo;
- ausência de associação explícita deve resultar em negação;
- não é permitido inferir autorização a partir apenas do fato de o usuário ter criado um paciente ou um leito.

Se a implementação exigir persistir associações usuário↔local, isso deverá ser introduzido como modelo simples e auditável na própria Spec 002, sem alterar a semântica do PEP.

## Grupos operacionais recomendados

A configuração inicial pode provisionar grupos Django independentes, permitindo composição de funções sem criar novos valores em `CustomUser.nivel_permissao`:

- `ADT - Consulta de Leitos` → `view_bed_map`;
- `ADT - Admissão` → `view_bed_map`, `admit_patient`, `view_movement_history`;
- `ADT - Transferência` → `view_bed_map`, `transfer_patient`, `view_movement_history`;
- `ADT - Alta` → `view_bed_map`, `discharge_patient`, `view_movement_history`;
- `ADT - Gestão de Leitos` → `view_bed_map`, `manage_bed_status`.

A composição de grupos não substitui as verificações ABAC sobre paciente, encontro, admissão e local.

## Respostas de autorização

- não autenticado: redirecionar para login;
- autenticado sem capacidade para uma tela administrativa genérica: `403`;
- objeto clínico fora do escopo e cuja existência não deve ser revelada: `404`;
- conflito de estado/concorrência após autorização: erro de domínio seguro (`409` sem API pública não é obrigatório; em views HTML, erro de formulário/flash sem detalhes de banco).

## Auditoria

Devem ser auditados:

- leitura de mapa quando houver PHI identificável renderizada;
- abertura de histórico ADT identificável;
- admissão, transferência, alta e mudança de status de leito;
- negações relevantes de operações críticas quando úteis à segurança, sem registrar PHI textual.

Payloads de auditoria e eventos devem usar IDs técnicos, códigos de ação/estado e timestamps; nome, CPF, diagnóstico e `reason` permanecem fora de logs técnicos e eventos assíncronos.

## Testes obrigatórios

A implementação deve provar, no mínimo:

- `CLI` negado em todas as superfícies ADT;
- `FUNC` sem permissão negado mesmo com acesso PEP;
- `FUNC` com permissão mas sem grant PEP vê somente estado mínimo do mapa e não pode mutar a internação;
- grant PEP expirado revoga imediatamente a superfície identificável;
- permissão de gestão de leito não concede acesso ao prontuário;
- revogação de permissão/grant é respeitada em refresh HTMX/WebSocket;
- tentativa de forjar UUID/ID de outro paciente/local não ultrapassa selectors/services autorizados.
