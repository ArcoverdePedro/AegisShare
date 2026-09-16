# Contrato — Administração de Medicamento

## Objetivo

Registrar de forma rastreável uma administração **efetivamente confirmada** à beira do leito, sem duplicar prescrição, dispensação, medicamento ou lote e sem inventar políticas clínicas ainda não aprovadas.

> Implementação T-NUR-10: núcleo online concluído. Auditoria explícita de leitura/mutação e emissão de `nursing.medication.administered` permanecem deliberadamente no T-NUR-12.

## Pré-condições

- usuário autenticado;
- capacidade `nursing.administer_medication`;
- escopo PEP válido para o paciente do encontro;
- `Encounter` aberto;
- `MedicationDispenseItem` existente e acessível;
- dispensação ligada a `MedicationRequest` do mesmo encontro;
- prescrição permanece `VALIDATED` no momento da confirmação;
- `request_item`, dispensação e lote preservam a cadeia de medicamento esperada;
- requisição feita online.

A implementação revalida essas condições no POST, dentro da operação de domínio; não confia apenas no GET anterior.

## Entrada v1

```text
dispense_item_id
administered_at
administered_dose
administered_dose_unit
operation_key
confirm = true
```

Não aceitar nome de paciente, medicamento, lote ou prescrição enviados pelo cliente como fonte de verdade. Esses vínculos são derivados do `dispense_item_id` no servidor.

## Semântica v1

A existência de `MedicationAdministration` significa apenas:

> um profissional autorizado confirmou que uma dose informada foi administrada naquele horário, vinculada ao item dispensado indicado.

A v1 **não modela** recusa, omissão, atraso, justificativa, erro, substituição ou administração parcial como estados clínicos. Esses conceitos dependem de política institucional e devem entrar em revisão posterior desta spec.

## Dose e unidade

- dose deve ser positiva;
- unidade deve ser explícita;
- nenhuma conversão automática de unidade;
- nenhuma equivalência terapêutica inferida;
- nenhuma recomendação de dose;
- divergência entre dose prescrita e informada não pode ser “corrigida” automaticamente pelo sistema.

Antes de suportar formalmente dose divergente como fluxo legítimo, a governança deve definir semântica, autorização e auditoria correspondentes. A UI v1 deixa claro que o fluxo suportado é confirmação de administração conforme o ato efetivamente realizado, sem oferecer mecanismo de ajuste terapêutico.

## Integridade temporal técnica

Sem implementar janela terapêutica ou horário programado, a confirmação recusa somente incoerências técnicas básicas:

- horário futuro;
- horário anterior ao início do encontro;
- horário anterior à própria dispensação.

Checagem de atraso, horário previsto, janela de administração ou decisão clínica continua fora da v1.

## Idempotência

`operation_key` é UUID única.

- primeiro POST válido cria a administração;
- retry com mesma chave e mesmos dados reconhece o registro existente;
- mesma chave apontando para entrada incompatível gera conflito seguro;
- retry revalida autorização e estado atual antes de reconhecer o registro existente;
- refresh/double-click não pode produzir administração duplicada.

## Rastreabilidade

A administração permite reconstruir:

```text
ator + horário
  -> MedicationAdministration
  -> MedicationDispenseItem
  -> Lot
  -> MedicationRequestItem
  -> MedicationRequest
  -> Encounter
  -> Patient
```

Nenhum desses dados é copiado desnecessariamente para a tabela de administração.

## Offline

Proibido nesta versão.

- formulário não registra listener de fila offline;
- POST falha sem rede;
- Cache Storage não recebe a mutação;
- IndexedDB `aegisshare-offline` não recebe envelope de administração;
- Background Sync não confirma administração;
- a superfície de administração não carrega `offline_queue.js` nem `vitals_offline.js`.

## Auditoria e evento

T-NUR-12 deve, após commit bem-sucedido:

- tornar leitura/mutação explicitamente auditável com ator correto;
- emitir `nursing.medication.administered` com IDs técnicos e timestamp;
- não incluir nome do paciente, dose, unidade, medicamento, lote textual ou instrução clínica no evento genérico.

## Erros seguros

- fora de escopo: 404/negação sem PHI;
- encontro fechado ou prescrição não mais validada: negação/conflito seguro;
- dispense item incompatível: conflito/404 sem detalhes de outro paciente;
- operation key conflitante: conflito idempotente;
- indisponibilidade de rede: nenhuma confirmação local.

## Gates futuros

Exigem revisão clínica/operacional antes de implementação:

- recusa/omissão;
- atraso;
- administração parcial;
- dose divergente e respectiva justificativa;
- checagens de horário/janela terapêutica de administração;
- identificação por código de barras;
- checagens automáticas de “certos” de medicação;
- administração de medicamento trazido pelo paciente ou fora do estoque/dispensação AegisShare;
- qualquer administração offline.
