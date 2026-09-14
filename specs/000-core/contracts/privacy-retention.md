# Inventário de privacidade e retenção inicial — Core

## Objetivo e escopo

Este documento fecha a T-CORE-09 com um inventário técnico dos dados tratados pelo Core e uma política inicial de retenção compatível com os controles já existentes no AegisShare.

Ele **não substitui avaliação jurídica, registro de operações de tratamento, bases legais, prazos regulatórios ou política institucional definitiva**. Esses pontos permanecem como responsabilidade da futura Spec 013 de LGPD/compliance, especialmente para dados clínicos. O objetivo aqui é impedir retenção indefinida por acidente, tornar lacunas explícitas e estabelecer limites técnicos seguros até a política definitiva.

## Princípios técnicos

O Core deve aplicar os seguintes princípios em código, operação e observabilidade:

1. coletar e persistir somente dados necessários à função do produto;
2. não usar templates como fronteira de autorização; toda leitura/escrita sensível deve ser validada no backend;
3. criptografar conteúdo de documentos antes do armazenamento externo;
4. não registrar segredos, tokens completos, senhas, chaves, conteúdo de arquivos ou conteúdo clínico em logs;
5. não replicar dados sensíveis em notificações, eventos, cache, analytics ou Sentry sem necessidade explícita;
6. preferir inativação/revogação e expurgo controlado a exclusões em cascata que destruam rastreabilidade necessária;
7. separar retenção operacional de retenção de auditoria;
8. toda rotina automática de expurgo deve ser idempotente, observável e conservadora quando o provedor externo falhar.

## Inventário técnico do Core

| Classe | Exemplos atuais | Finalidade técnica | Sensibilidade | Persistência atual | Regra inicial |
|---|---|---|---|---|---|
| Identidade e conta | username, nome, e-mail, telefone, foto, papel/permissão | autenticação, identificação e autorização | pessoal | PostgreSQL | manter enquanto a conta for necessária; desativação deve preceder exclusão física quando houver vínculos de auditoria |
| Credenciais | hash de senha do Django | autenticação | segredo derivado | PostgreSQL | nunca exportar para logs; removido somente com a conta e conforme dependências permitirem |
| 2FA e recuperação | segredo TOTP cifrado, códigos de recuperação | autenticação forte | segredo | PostgreSQL | manter apenas enquanto 2FA estiver habilitado/necessário; nunca registrar em auditlog/logs |
| Sessões | session key, IP, user-agent, timestamps, revogação | segurança de sessão e inventário de dispositivos | pessoal/segurança | sessão Django + `TrackedSession` | sessões revogadas/expiradas são candidatas a expurgo periódico; prazo final será parametrizado em implementação específica |
| Tokens de API legados | nome, prefixo, hash, criação, último uso, expiração, revogação | compatibilidade da API em descontinuação | segurança | PostgreSQL | token completo nunca é persistido; metadados permanecem durante a migração da API e podem ser expurgados depois do período operacional definido pela Spec 013 |
| Workspaces e membros | cliente, membros, `can_upload`, `can_share` | organização e autorização | pessoal/organizacional | PostgreSQL | manter enquanto houver relação operacional; remoção não pode ampliar acesso residual |
| Metadados de documentos | nome, MIME, tamanho, descrição, tags, proprietário, datas | gestão documental | potencialmente pessoal/confidencial | PostgreSQL | acompanha o ciclo de vida do documento e a lixeira |
| Conteúdo de documentos | bytes do arquivo | armazenamento/compartilhamento | potencialmente sensível | Pinata/IPFS, cifrado em novos uploads | lixeira por prazo configurável e expurgo externo antes da remoção definitiva local |
| Criptografia de documentos | wrapped key, hashes, CID, flags de versão | confidencialidade e integridade | segurança | PostgreSQL | preservar enquanto a versão correspondente existir; nunca registrar `wrapped_key` em auditlog |
| Concessões e links | `FileAccess`, prefixo/hash de link, senha em hash, expiração, limites, revogação | compartilhamento | segurança/pessoal | PostgreSQL | revogação deve retirar acesso imediatamente; tokens completos não são persistidos |
| Solicitações de documentos | destinatário, criador, título, descrição, itens, status | colaboração | potencialmente pessoal | PostgreSQL | acompanha relação operacional; política definitiva de expurgo fica para Spec 013 |
| Comentários e chat | comentários, mensagens, participantes, vínculo com arquivo | colaboração | potencialmente confidencial | PostgreSQL | não criar cópias em logs/notificações; retenção definitiva depende da política institucional e Spec 013 |
| Notificações | tipo, título, corpo, link, leitura | UX e acompanhamento | potencialmente pessoal | PostgreSQL | não reproduzir conteúdo sensível; prazo de expurgo ainda é uma lacuna de implementação |
| Auditoria | ator, objeto, ação, timestamps e metadados do `django-auditlog` | rastreabilidade e segurança | pessoal/segurança | PostgreSQL | retenção separada do dado operacional; campos sensíveis devem permanecer excluídos/masked; prazo definitivo depende da Spec 013 |
| Logs/Sentry | nível, erro, request metadata quando disponível | operação e diagnóstico | potencialmente pessoal | stdout/coletor/Sentry opcional | minimizar; não incluir tokens, chaves, conteúdo de arquivo, credenciais ou dados clínicos; prazo deve ser configurado no provedor |

## Dados clínicos: fronteira explícita

O domínio PEP não recebe um prazo definitivo por este contrato. A Spec 001 já determina preservação de vínculos clínicos, imutabilidade de evoluções e ausência de dados clínicos identificáveis em logs/notificações. Exportação, anonimização, retenção definitiva e direitos do titular permanecem para a Spec 013.

Portanto:

- o Core não deve criar jobs genéricos que apaguem `Patient`, `Encounter` ou `ClinicalEvolution`;
- a exclusão ou anonimização de conta não pode destruir automaticamente vínculos clínicos protegidos;
- qualquer rotina futura de direito do titular deve distinguir dados operacionais, auditoria necessária e prontuário clínico antes de alterar registros.

## Política inicial de retenção

### 1. Documentos na lixeira — controle já implementado

`FILE_RETENTION_DAYS` é o controle canônico da lixeira e possui baseline de **30 dias** no ambiente de exemplo/settings. O comando `purge_trash` usa esse valor como padrão.

Regras:

- `soft_delete` retira o arquivo das superfícies normais imediatamente;
- durante a janela de retenção, apenas o escopo autorizado de lixeira pode restaurá-lo;
- após a janela, o expurgo deve tentar remover cada objeto externo correspondente;
- se a remoção no provedor externo falhar, o registro local deve ser preservado e a operação deve falhar de forma observável, evitando perder a referência necessária a nova tentativa;
- alteração do prazo deve ser configuração operacional, nunca constante espalhada no código.

### 2. Links e grants

Revogar acesso é uma ação de autorização e deve produzir efeito imediato, independentemente de qualquer política de retenção histórica.

- `FileAccess` deixa de autorizar assim que é removido;
- `SharedLink.revoked_at`, expiração, limite de downloads e flags de preview/download são fronteiras de acesso, não apenas atributos de interface;
- token completo e senha em claro não devem ser armazenados;
- a eventual limpeza de links antigos poderá remover metadados inativos, mas somente depois de definido o prazo institucional de rastreabilidade.

### 3. Sessões e tokens

O produto já suporta revogação. Retenção física é tratada como lacuna controlada nesta fase:

- sessão/token revogado ou expirado nunca deve recuperar validade por limpeza de cache ou mudança de UI;
- hashes não devem ser convertidos novamente em material autenticador;
- jobs de expurgo de `TrackedSession` e `APIToken` serão implementados apenas após parametrização de prazo e testes de auditoria;
- enquanto isso, os registros devem permanecer minimizados e inacessíveis a usuários sem permissão administrativa.

### 4. Comentários, chat, solicitações e notificações

Não há, nesta iteração, prazo automático seguro para excluir esses registros sem risco de quebrar contexto documental ou rastreabilidade. A política inicial é:

- não criar retenção infinita implícita como requisito de produto;
- registrar esta ausência como gap de implementação;
- impedir replicação desnecessária desses conteúdos em logs/cache/eventos;
- fechar prazo, anonimização e regras de exclusão na Spec 013 antes de ativar um job destrutivo.

### 5. Auditoria

Auditoria não segue automaticamente o prazo do objeto operacional.

- excluir um documento, grant ou conta não autoriza apagar silenciosamente o histórico necessário à rastreabilidade;
- campos já classificados como segredo ou conteúdo sensível devem continuar excluídos/masked no `django-auditlog`;
- o prazo institucional de auditoria deve ser definido na Spec 013 antes de qualquer expurgo;
- nenhuma rotina de limpeza pode apagar auditlog em cascata sem revisão explícita.

### 6. Logs, observabilidade e Sentry

A política inicial é de **minimização na origem**:

- não registrar bodies de upload/download;
- não registrar `Authorization`, cookies, senha, códigos 2FA, recovery codes, token completo de API/link, `SECRET_KEY`, `FILE_ENCRYPTION_KEY` ou `wrapped_key`;
- não registrar CPF, diagnóstico, motivo clínico, conteúdo de evolução ou conteúdo de documentos;
- URLs e mensagens de erro devem ser revisadas para não transportar tokens completos;
- retenção do coletor/Sentry é configuração externa e deve constar do inventário operacional da Spec 013.

## Matriz de implementação

| Controle | Estado | Evidência/ação |
|---|---|---|
| lixeira com retenção configurável | implementado | `FILE_RETENTION_DAYS` + `purge_trash` |
| preservação local se remoção externa falhar | implementado | `purge_expired_trash`/`purge_trash` |
| conteúdo de novos arquivos cifrado antes do IPFS | implementado | serviço de arquivos e `FileVersion` |
| hashes/segredos excluídos do auditlog | implementado parcialmente por modelo | registros do `auditlog.register(...)` |
| autorização por objeto no backend | implementado/revisado em T-CORE-07 | selectors/services/views + testes |
| cache PWA sem dados sensíveis autenticados | implementado/testado | Spec 014 + Playwright |
| expurgo de sessões antigas | gap | criar tarefa de implementação após definição de prazo |
| expurgo de tokens API revogados/expirados | gap | coordenar com remoção da API legada |
| expurgo de notificações | gap | prazo a definir na Spec 013 |
| retenção de comentários/chat | gap | prazo/regra de anonimização a definir na Spec 013 |
| prazo de auditlog | gap deliberado | decisão institucional/Spec 013 antes de automação |
| direitos do titular/exportação/anomização | fora desta tarefa | Spec 013 |
| retenção clínica definitiva | fora desta tarefa | Spec 013 + Spec 001 |

## Gates para qualquer novo job de expurgo

Um job destrutivo novo só pode ser mergeado quando:

1. o conjunto de dados e o prazo estiverem documentados;
2. relações `CASCADE`, `PROTECT`, M2M e auditlog tiverem sido avaliadas;
3. existir modo dry-run ou consulta equivalente para estimar impacto;
4. houver testes para fronteiras temporais e idempotência;
5. falha de provedor externo não provocar perda irreversível da referência local;
6. logs do job não contiverem dados sensíveis;
7. rollback ou procedimento de restauração estiver documentado para o tipo de dado aplicável.

## Decisões adiadas de propósito

Esta tarefa não inventa prazos jurídicos. Permanecem para a Spec 013 e validação do mantenedor/organização:

- prazo definitivo de auditlog;
- prazo de sessões e metadados de segurança;
- prazo de chat, comentários, notificações e solicitações;
- política de backup e prazo de cópias de segurança;
- exportação/portabilidade e fluxo de atendimento ao titular;
- anonimização e exclusão de contas com dependências históricas;
- retenção e descarte de dados clínicos;
- inventário de subprocessadores/provedores e respectivos prazos.

## Critério de conclusão da T-CORE-09

T-CORE-09 é considerada concluída quando este inventário estiver versionado e revisado. A conclusão significa que o Core possui **baseline técnico e gaps explícitos**; não significa conformidade jurídica integral nem autoriza apagar dados clínicos ou de auditoria sem a Spec 013.
