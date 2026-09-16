# Plano técnico — Spec 012 v1

Status: recorte v1 aprovado em 2026-09-16 e implementado. Evidências em `validation.md`.

## Arquitetura e reuso

Nível usado: **1/2/3 — reuso do projeto + Django nativo + FBV**. App `apps/interoperability` criado após aprovação. Reusar `Patient`, `accessible_patients`, `is_internal_professional`, sessão/CSRF e auditlog. A serialização explícita fica na própria FBV, pois atende um único fluxo; sem helper ou framework de adaptadores.

## Modelo de Dados

`PatientExportReceipt`, conforme `data-model.md`, registra metadados técnicos sem armazenar JSON clínico. A capacidade de exportação pertence ao model via `Meta.permissions`; nenhum grupo recebe a capacidade automaticamente.

## Rotas, Views e Forms

Contratos em `contracts/routes.md` e `contracts/forms.md`. A FBV usa decorators nativos para sessão e GET/POST; verifica profissional/capacidade antes de consultar dados. O `ModelChoiceField` recebe o queryset PEP em cada request. POST inválido retorna HTML 200 com erros, sem recibo. POST válido gera attachment 200.

GET com permissão revogada recebe 403; POST também. Sem sessão, redirect ao login. Paciente inválido/fora do escopo produz a mesma mensagem no campo. Reavaliar o escopo imediatamente antes da serialização; alterações concorrentes obedecem à autorização observada na transação, sem prometer revogação retroativa de arquivo já entregue.

## Exportação e auditoria

1. Validar formulário e autorização atual.
2. Construir o recurso a partir da allowlist e serializar em bytes UTF-8.
3. Em `transaction.atomic()`, criar recibo com digest dos bytes e auditoria sob `set_actor(user)`; registrar `ACCESS` do paciente pelo mecanismo existente.
4. Somente após persistência bem-sucedida, retornar bytes com `HttpResponse`, MIME e attachment definidos no contrato.

Não executar download em streaming: o arquivo é pequeno e já está em memória. Não persistir temporário/IPFS nem logar payload. POST repetido gera novo recibo legítimo de exportação; não há mutação clínica que requeira idempotência.

## Templates e componentes HTMX

Reusar layout e estilo vigentes, sem migração visual. Formulário HTML nativo, sem fragmento HTMX: submissão normal permite download. Opções exibem nome e UUID para desambiguação, sem CPF. Na v1 o queryset de seleção usa os pacientes acessíveis; medir volume antes de introduzir autocomplete.

## Eventos internos

Nenhum consumidor assíncrono atual exige evento. O contrato `contracts/events.md` define apenas auditoria persistente nesta versão; WebSockets, Celery e Redis Streams não são acrescentados.

## PWA e segurança

`/interop/` permanece network-only. Validar política do service worker existente e cabeçalhos em sucesso, erro e negação. Não adicionar operation type à fila IndexedDB. Testar ausência de PHI em caches/armazenamento local e logs. Exportação usa sessão e CSRF, sem ampliar allowlist de API legada.

## Migrações

Uma migration inicial para recibo e permissão; FKs PROTECT. Reversão técnica testada em banco descartável. Após uso real, rollback de aplicação preserva recibos; não executar reversão destrutiva automaticamente.

## Testes e rollout

Usar o runner Django e Playwright já adotados. Cobrir a matriz da spec, inclusive falha de auditoria, revogação entre GET/POST, attachment e CSRF com verificação habilitada. Fixtures exclusivamente sintéticas. Validar estrutura contra a versão fixa do contrato; não alegar certificação FHIR ou perfil nacional.

Executar gates existentes de CI antes de habilitar a capacidade em ambiente piloto. Gates SAST/SCA/compliance ausentes no ambiente devem ser relatados como não executados; não marcar DoD por inferência. Lighthouse verifica regressão da PWA existente; não afirmar aprovação por score não medido.

Rollout: aprovação → código/migration → testes → piloto com dados sintéticos → autorização institucional separada para dados reais. Depois, elaborar extensão de ingestão HL7/ASTM com schemas, identificação, duplicidade, quarentena e semântica de resultados antes da Spec 005.
