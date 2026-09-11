# Mapeamento de modelos e migração incremental de apps

Status: plano arquitetural da Spec 000. Este documento atende T-CORE-05 e T-CORE-06. Ele **não move tabelas nem altera `app_label`** por si só.

## Objetivo

Separar gradualmente o monólito legado `aegis_share` em responsabilidades mais explícitas (`core`, `documents` e `audit`) sem renomear tabelas, perder histórico de auditoria ou introduzir uma migração de banco de alto risco.

A regra principal é: **primeiro separar código e dependências; mover ownership de modelos somente depois que imports, serviços e testes estiverem estáveis**.

## Mapeamento atual -> responsabilidade alvo

### `core`

| Modelo atual | Papel | Destino lógico |
|---|---|---|
| `CustomUser` | identidade, papéis e autenticação | `core.identity` |
| `Workspace` | limite organizacional por cliente | `core.workspaces` |
| `WorkspaceMember` | associação e capacidades do workspace | `core.workspaces` |
| `Notification` | notificações internas | `core.notifications` |
| `UserSecuritySettings` | TOTP e recuperação | `core.security` |
| `TrackedSession` | inventário/revogação de sessões | `core.security` |
| `APIToken` | compatibilidade da API legada | `core.security` enquanto existir |
| `Conversation` | colaboração em tempo real | `core.collaboration` |
| `Message` | mensagens de conversa | `core.collaboration` |

`APIToken` permanece associado ao Core apenas durante a janela de compatibilidade da API legada. Sua remoção futura depende do gate descrito em `api-deprecation.md`.

### `documents`

| Modelo atual | Papel | Destino lógico |
|---|---|---|
| `Folder` | hierarquia documental dentro de workspace | `documents.organisation` |
| `Tag` | classificação documental | `documents.organisation` |
| `IPFSFile` | agregado principal de documento/arquivo | `documents.models` |
| `FileVersion` | versão, hashes, CID e envelope de chave | `documents.models` |
| `FileAccess` | concessão explícita de acesso | `documents.permissions` |
| `SharedLink` | compartilhamento público controlado | `documents.sharing` |
| `FileComment` | colaboração vinculada ao documento | `documents.comments` |
| `DocumentRequest` | solicitação de documentos ao cliente | `documents.requests` |
| `DocumentRequestItem` | item de solicitação e vínculo ao arquivo entregue | `documents.requests` |

Embora `Folder` dependa de `Workspace`, o workspace continua sendo responsabilidade do Core; `documents` referencia o limite organizacional, mas não o possui.

### `audit`

O histórico principal não é um modelo próprio de `aegis_share`: ele usa `django-auditlog` e `auditlog.models.LogEntry`. O destino lógico `audit` deve concentrar:

- registro/configuração dos modelos auditados;
- consulta administrativa e filtros de auditoria;
- eventos explícitos de leitura/acesso;
- políticas de mascaramento/exclusão de campos sensíveis;
- integração com eventos internos/AsyncAPI quando aplicável.

**Não copiar nem recriar `LogEntry`.** A implementação deve reutilizar a tabela do pacote e preservar os `ContentType` associados ao histórico existente.

### Clínico/PEP

`Patient`, `PatientAccessGrant`, `Encounter` e `ClinicalEvolution` já pertencem a `apps.clinical.pep` e **não devem ser absorvidos** por `core` ou `documents`. Eles dependem de serviços transversais do Core (identidade, autorização, auditoria e eventos), mas mantêm ownership clínico. A separação deve evitar qualquer import de domínio clínico de volta para `core`/`documents`.

## Dependências desejadas

```text
apps.clinical.pep
      |        \
      v         v
    core ---> documents
      \         /
       v       v
         audit

infraestrutura externa (Pinata, Redis, Sentry, ClamAV)
fica atrás de adapters/services e não define ownership de domínio.
```

Regras:

1. `core` não importa modelos clínicos.
2. `documents` pode depender de identidade/workspace do `core`, nunca do PEP.
3. PEP pode consumir serviços públicos de `core` e `documents` quando necessário.
4. `audit` observa os domínios, mas não contém regra de negócio documental ou clínica.
5. Views/templates não devem ser a fonte de verdade para autorização; selectors/services permanecem responsáveis pelos limites de objeto.

## Estratégia de migração incremental

### Etapa 1 — criar fronteiras sem mover modelos

Criar pacotes/apps alvo e mover primeiro código sem estado de banco: services, selectors, adapters, views auxiliares e testes. Durante essa etapa, os modelos continuam fisicamente em `aegis_share.models`.

Preferir imports por fachadas estáveis, por exemplo:

```python
from apps.documents.services import create_file_from_upload
```

A fachada pode delegar temporariamente à implementação legada. Isso reduz a quantidade de imports que precisarão mudar na etapa de ownership dos modelos.

**Rollback:** reverter somente imports/fachadas; nenhuma tabela ou migration muda.

### Etapa 2 — separar `audit`

Mover a tela/serviços de consulta de auditoria e centralizar os registros `auditlog.register(...)` sem trocar os modelos auditados. Adicionar testes que garantam que eventos anteriores continuam consultáveis e que campos sensíveis continuam mascarados/excluídos.

**Rollback:** recolocar registro e views no módulo anterior; histórico permanece intacto.

### Etapa 3 — separar services/selectors de documentos

Mover criptografia de fluxo, Pinata, políticas de arquivo, compartilhamento, solicitações e selectors para a fronteira `documents`, mantendo as tabelas atuais. Adaptadores externos devem continuar mockáveis nos testes.

Nessa etapa, validar explicitamente:

- upload, versionamento, preview e download;
- concessão/revogação de acesso;
- links compartilhados;
- lixeira e expurgo;
- solicitações de documentos;
- chat associado a arquivo;
- auditoria de criação/leitura.

**Rollback:** fachadas apontam novamente para módulos legados.

### Etapa 4 — preparar ownership dos modelos

Antes de mover qualquer classe entre apps:

1. registrar o nome físico de todas as tabelas, constraints e índices existentes;
2. adicionar testes de schema/`makemigrations --check`;
3. congelar mudanças concorrentes nos modelos envolvidos durante o PR de transição;
4. identificar todas as referências de `ContentType`, permissões Django e `LogEntry` aos modelos que mudarão de `app_label`;
5. criar backup testável e ensaiar a migration numa cópia representativa do banco.

Nenhuma tabela deve ser renomeada apenas para refletir o novo nome do app.

### Etapa 5 — mover ownership de modelos sem mover dados

O movimento deve ser feito em lotes pequenos, começando por modelos com menos dependências. O PR de cada lote deve preservar o `db_table` físico atual e usar migrations de estado controladas (por exemplo, `SeparateDatabaseAndState` quando adequado), em vez de `CreateModel`/`DeleteModel` que tentem recriar tabelas existentes.

O plano da migration deve tratar explicitamente:

- `django_content_type` do app antigo e novo;
- `auth_permission` associado aos content types;
- FKs de `django-auditlog`/`LogEntry` para content types;
- relações ManyToMany e modelos `through` (`WorkspaceMember`, `FileAccess`);
- nomes de constraints e índices já existentes;
- histórico de migrations do app legado, que não deve ser apagado.

A mudança de content type deve possuir `RunPython` reversível quando houver remapeamento de dados. Não executar `remove_stale_contenttypes` durante a transição antes de confirmar que o histórico foi remapeado.

**Rollback:** migration reversa restaura os content types/estado Django e os imports anteriores, mantendo as mesmas tabelas físicas.

### Etapa 6 — remover fachadas legadas

Somente após pelo menos um ciclo estável com os novos apps:

- remover reexports/imports de compatibilidade sem consumidores;
- remover módulos legados vazios;
- manter migrations históricas versionadas;
- atualizar documentação arquitetural e diagramas;
- executar testes completos e restauração de backup em ambiente de validação.

## Ordem sugerida de lotes de modelos

A ordem abaixo reduz acoplamento; não é autorização automática para executar todos os lotes no mesmo PR:

1. `Notification`, `UserSecuritySettings`, `TrackedSession` -> `core`;
2. `Conversation`, `Message` -> `core.collaboration`;
3. `Tag`, `Folder`, `FileComment` -> `documents`;
4. `DocumentRequest`, `DocumentRequestItem` -> `documents`;
5. `IPFSFile`, `FileVersion`, `FileAccess`, `SharedLink` -> `documents`;
6. `Workspace`, `WorkspaceMember` -> `core.workspaces`;
7. `CustomUser` por último, porque `AUTH_USER_MODEL`, permissões e várias FKs tornam essa mudança a de maior impacto.

`APIToken` não deve ser movido apenas para ser removido logo depois; decidir seu destino depois do inventário operacional da API legada.

## Gates obrigatórios por lote

Um lote de migração só pode ser mergeado quando:

- `manage.py check` e `makemigrations --check --dry-run` não apontarem drift inesperado;
- migrations forem aplicadas do zero e sobre banco atualizado da versão anterior;
- migration reversa for testada quando tecnicamente suportada;
- quantidade de registros por tabela for igual antes/depois quando não houver transformação de dados;
- relações e permissões por objeto continuarem cobertas por testes;
- auditoria histórica anterior ao move continuar acessível;
- Docker smoke test e suíte completa passarem.

## O que este plano deliberadamente não faz

- não renomeia tabelas;
- não altera `AUTH_USER_MODEL` agora;
- não move os modelos clínicos;
- não apaga migrations antigas;
- não remove a API legada;
- não cria uma migração monolítica de todos os modelos.

Essas restrições preservam rollback e reduzem o risco de indisponibilidade ou perda de histórico durante a reorganização arquitetural.
