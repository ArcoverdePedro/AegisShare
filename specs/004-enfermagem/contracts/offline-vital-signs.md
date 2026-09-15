# Contrato — Piloto Offline de Sinais Vitais

## Escopo aprovado pela Spec 004 proposta

Única operação clínica offline desta spec:

```text
operation_type = nursing.vitals.record
```

A aprovação deste contrato **não** autoriza administração de medicamento offline nem outras mutações clínicas.

## Infraestrutura

Reutilizar integralmente `static/pwa/offline_queue.js` e o envelope definido pela Spec 014. Não criar outro IndexedDB, outra chave criptográfica ou outro mecanismo de retry.

## Payload clínico mínimo

Após descriptografia no cliente autorizado, o payload pode conter somente:

```text
encounter_id
recorded_at
replaces_id optional
measurements:
  temperature_c optional
  heart_rate_bpm optional
  respiratory_rate_irpm optional
  systolic_bp_mmhg optional
  diastolic_bp_mmhg optional
  oxygen_saturation_pct optional
  weight_kg optional
```

`idempotency_key`, `operation_type` e `user_session_fingerprint` permanecem no envelope autenticado da Spec 014.

Não incluir nome, CPF, endereço, texto livre, diagnóstico ou medicamento.

## Criação local

1. O formulário usa as mesmas validações estruturais possíveis no navegador apenas para UX.
2. A fonte de verdade da validação continua sendo o servidor.
3. Sem rede, a operação é serializada e cifrada pela fila existente.
4. O navegador mostra estado pendente sem alegar que o prontuário já foi atualizado no servidor.
5. Logout limpa a fila vinculada à sessão conforme contrato PWA.

## Sincronização

Ao reconectar:

1. confirmar sessão autenticada;
2. enviar uma operação por `idempotency_key`;
3. servidor revalidar capacidade `record_vitals`;
4. servidor revalidar escopo PEP;
5. servidor revalidar existência e estado do `Encounter`;
6. servidor executar o mesmo form/service usado no fluxo online;
7. persistir atomicamente o registro e a chave idempotente;
8. somente após resposta de sucesso marcar/remover o envelope local conforme política PWA.

## Idempotência

- mesma `idempotency_key` + mesma operação já confirmada: devolver reconhecimento do registro existente, sem duplicar;
- mesma chave com payload incompatível: conflito seguro; não sobrescrever;
- falha de rede após commit pode provocar retry, mas nunca segundo registro.

## Conflitos

Estado `conflict` exige revisão explícita quando, entre criação local e sincronização:

- encontro foi encerrado;
- acesso PEP foi perdido;
- sessão/identidade mudou;
- `replaces_id` deixou de ser elegível;
- servidor detectar colisão semântica de `idempotency_key`.

Não usar `last-write-wins`.

Como sinais vitais são append-only, sincronização não atualiza linha clínica existente. Correção posterior cria novo registro.

## Segurança

- Cache Storage não armazena POST/payload clínico;
- IndexedDB armazena apenas ciphertext + metadados mínimos já contratados;
- logs do service worker não imprimem payload;
- erro de sync não devolve PHI em mensagem técnica;
- a chave não extraível no IndexedDB reduz exposição casual, mas não substitui CSP/XSS defenses já previstas pela Spec 014.

## Testes obrigatórios antes de habilitar

- ciphertext não contém valores em texto claro pesquisável;
- mesmo envelope sincronizado duas vezes cria uma linha;
- queda de conexão após envio não duplica no retry;
- encontro fechado vira conflito, não insert silencioso;
- perda de permissão vira bloqueio;
- logout remove dados locais da sessão;
- administração de medicamento não entra na fila;
- axe/Playwright em viewport mobile para estados online, pendente, synced e conflict.
