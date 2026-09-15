# Contrato — Sincronização Offline

## Princípio

Offline é uma exceção controlada por requisito clínico. Nenhum formulário autenticado entra em fila offline automaticamente.

## Envelope local mínimo

```text
idempotency_key
operation_type
created_at
user_session_fingerprint
payload_ciphertext
status: pending|syncing|synced|conflict|failed
retry_count
```

## Regras

1. Cada operação recebe `idempotency_key` única.
2. O payload deve conter apenas os campos necessários ao fluxo aprovado.
3. Dados sensíveis persistidos localmente devem estar protegidos; nunca em texto claro.
4. Ao reconectar, o cliente revalida sessão antes de sincronizar.
5. Se a sessão expirou, a operação permanece bloqueada até nova autenticação; não enviar anonimamente.
6. A view Django reaplica autorização e validação completa no servidor.
7. Reenvio com a mesma `idempotency_key` não pode duplicar o registro.
8. Conflitos devem ser auditados. `last-write-wins` só pode ser usado quando a spec do fluxo permitir; caso contrário exige revisão manual.
9. Sucesso confirmado remove ou minimiza o payload local conforme política de retenção.
10. Logout limpa payloads locais da sessão, salvo mecanismo institucional explicitamente aprovado para recuperação segura.

## Fundação local implementada

`static/pwa/offline_queue.js` implementa o armazenamento local protegido sem habilitar nenhum fluxo clínico automaticamente.

- o IndexedDB canônico é `aegisshare-offline`, o mesmo removido pelo service worker durante a limpeza local;
- cada payload é serializado e cifrado com AES-GCM 256 antes da persistência;
- a chave é criada pela Web Crypto API como `CryptoKey` não extraível e persistida no próprio IndexedDB;
- um IV aleatório de 96 bits é usado por operação;
- `idempotency_key`, `operation_type` e `user_session_fingerprint` entram como Additional Authenticated Data (AAD), portanto alteração desses metadados invalida a autenticação do ciphertext;
- o object store usa `idempotency_key` como chave primária, rejeitando duplicatas no dispositivo;
- listagens comuns retornam somente metadados; a leitura do payload exige descriptografia explícita;
- nenhum listener intercepta formulários e nenhum envio de rede é feito pelo helper genérico.

A chave no IndexedDB protege o conteúdo contra persistência em texto claro e inspeção casual do armazenamento bruto, mas **não é uma fronteira contra XSS ou código comprometido executando na mesma origem**, que poderia solicitar a descriptografia pela Web Crypto API. CSP, prevenção de XSS, autorização no servidor e limpeza no logout continuam obrigatórias.

## Fluxos elegíveis

O primeiro e único piloto habilitado é:

```text
operation_type = nursing.vitals.record
```

A integração pertence à Spec 004 Enfermagem. Somente a tela de registro/correção de sinais vitais opta explicitamente pela fila; a sincronização usa rota Django interna autenticada por sessão + CSRF, compara o fingerprint da sessão e reaplica form, capacidade, escopo PEP, estado do encontro e idempotência server-side.

A habilitação deste piloto **não** torna outras mutações elegíveis. Cada novo fluxo continua exigindo aprovação explícita de sua própria spec.

## Fluxos proibidos por padrão

- assinatura clínica;
- exclusão/revogação de consentimento;
- administração de medicamento sem regra clínica específica;
- download de documento;
- alterações administrativas sensíveis;
- **admissão, transferência e alta ADT**: dependem do estado concorrente atual de leitos e permanecem `network-only` conforme RF-ADT-12; não podem usar Cache Storage, IndexedDB ou Background Sync para persistir a mutação.

A regressão ADT é exercitada por Playwright em `tests/e2e/adt_journeys.spec.js`: com service worker ativo, os POSTs críticos devem falhar quando a rede é removida e nenhuma entrada pode surgir no cache ou no IndexedDB `aegisshare-offline`.
