# Changelog

Todas as mudanças relevantes do AegisShare serão registradas neste arquivo.

## [0.2.0] - Em desenvolvimento

### Corrigido

- Atualização transitiva de `click` de 8.3.0 para 8.3.3 para corrigir o alerta `PYSEC-2026-2132` identificado pelo pip-audit.

### Adicionado

#### HIS clínico

- Spec 013: solicitações do titular com escopo PEP, histórico auditado, transições atômicas, conflito concorrente e fluxo exclusivamente online.
- Spec 012: exportação individual de cadastro mínimo FHIR R4 via formulário autenticado, com escopo PEP, CSRF, recibo auditado e proteção no-store.

- PEP com paciente e encontro canônicos, evolução clínica e adendos append-only.
- Autorização clínica RBAC + ABAC deny-by-default e auditoria de leitura/escrita.
- ADT com localização, leitos, admissão, transferência e alta transacionais.
- Mapa de leitos server-rendered com atualização por Channels e minimização de PHI.
- Prescrição estruturada com ciclo DRAFT/submissão, substituição rastreável e histórico imutável.
- Catálogo de medicamentos, referências versionadas, safety review determinístico e validação farmacêutica.
- Estoque farmacêutico por item/lote, ledger append-only e dispensação transacional/idempotente.
- Sinais vitais estruturados, correção por `replaces` e proveniência técnica de peso.
- Administração de medicamento vinculada à dispensação/lote, idempotente e exclusivamente online.
- Eventos internos clínicos pós-commit com payload técnico minimizado e contratos AsyncAPI.
- Cenários Gherkin, Playwright, axe-core e validação de telefone/tablet para as jornadas clínicas entregues.

#### PWA

- Manifest, service worker e fallback offline.
- Cache deny-by-default para conteúdo sensível.
- Fila IndexedDB com payload AES-GCM e chave não extraível.
- Piloto offline restrito a `nursing.vitals.record`, com idempotência e conflitos explícitos.
- Limpeza de cache/IndexedDB no logout.
- Web Push genérico sem PHI no payload.
- Gates E2E contra plaintext clínico em IndexedDB, Cache Storage, console e logs da stack.

#### Core e colaboração

- Criptografia AES-256-GCM antes do armazenamento no IPFS.
- Chave independente por versão e envelope encryption.
- SHA-256 e validação de integridade.
- Versionamento de documentos.
- `django-auditlog` e painel administrativo de auditoria.
- Workspaces, membros e pastas.
- Tags e busca ampliada.
- Links temporários com senha, expiração, limite de downloads e revogação.
- Comentários associados a arquivos.
- Solicitações de documentos e acompanhamento de pendências.
- Notificações internas.
- 2FA TOTP e códigos de recuperação.
- Inventário e revogação de sessões.
- Tokens de API armazenados como hash.
- Lixeira, restauração e política de retenção.
- ClamAV opcional.
- Sentry opcional e logs JSON.
- Endpoints de liveness/readiness/serviços.
- PostgreSQL configurável por `DATABASE_URL`.
- Redis configurável por `REDIS_URL`.
- Quatro topologias de Docker Compose.
- Testes de segurança, criptografia, permissões, compartilhamento e WebSocket.
- CI com PostgreSQL, Redis, Ruff, migrations, suíte Django, Compose, Playwright e Lighthouse.
- CodeQL e teste arquitetural que bloqueia novas rotas públicas `/api/` fora da allowlist legada.

### Alterado

- AegisShare passa a documentar explicitamente o escopo atual como HIS + plataforma segura de colaboração.
- As rotas públicas `api/v1/*` existentes passam a ser tratadas como compatibilidade legada em depreciação; novos módulos usam views/forms Django e integrações internas.
- Licença alterada de MIT para `AGPL-3.0-only`, com `NOTICE` preservando o copyright do projeto.
- Python de produção padronizado em 3.14.
- Views divididas em controllers sob `aegis_share/web/` no núcleo legado; módulos clínicos seguem organização por bounded context e FBV-first.
- Regras de negócio e integrações do núcleo documental movidas para `aegis_share/services/`.
- Política de upload centralizada.
- Acesso a arquivos novos deixa de apontar diretamente para gateways IPFS.
- Dockerfile convertido para build multi-stage.
- Redis e PostgreSQL internos deixam de publicar portas no host.
- Configuração de produção passa a falhar cedo quando segredos obrigatórios estão ausentes/inválidos.

### Segurança

- Corrigida autorização de WebSocket para impedir acesso a conversas de terceiros.
- Corrigida autorização de compartilhamento de arquivos.
- Tokens públicos/API não são persistidos em texto puro.
- Segredo TOTP é criptografado.
- Campos sensíveis são excluídos/mascarados no audit log.
- Uploads passam por validação de tamanho/MIME e podem passar por ClamAV.
- Superfícies clínicas combinam capacidade Django e escopo PEP, com negações sem eco de PHI.
- Operações clínicas persistidas adotam histórico append-only e chaves idempotentes nos fluxos contratados.
- Administração de medicamento, ADT e mutações de prescrição/dispensação permanecem fora da fila PWA.
- O piloto offline de sinais vitais mantém somente ciphertext no IndexedDB e revalida autorização/estado na sincronização.

### Compatibilidade

- Arquivos existentes são preservados como `FileVersion v1` legada e não criptografada.
- `aegis_share.views` permanece temporariamente como camada de compatibilidade para imports antigos.
- As três rotas públicas legadas de arquivos permanecem disponíveis enquanto seus consumidores não forem migrados; um teste de arquitetura impede expansão silenciosa dessa superfície.

### Governança clínica pendente

- Assinatura jurídica do PEP permanece bloqueada até validação jurídica/operacional externa.
- Conteúdo clínico real de referências de interação/dose permanece bloqueado até aprovação clínica/farmacêutica; o runtime não inventa regras terapêuticas.
- Consumo automático de `weight_kg` pelo RX permanece `NOT_EVALUABLE` até aprovação da política de origem/atualidade.
- Recusa, omissão, atraso, dose divergente e administração parcial permanecem fora do modelo de Enfermagem até definição institucional.
