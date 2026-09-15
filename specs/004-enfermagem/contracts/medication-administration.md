# Contrato — Administração de Medicamento

## Objetivo

Registrar de forma rastreável uma administração **efetivamente confirmada** à beira do leito, sem duplicar prescrição, dispensação, medicamento ou lote e sem inventar políticas clínicas ainda não aprovadas.

## Pré-condições

- usuário autenticado;
- capacidade `nursing.administer_medication`;
- escopo PEP válido para o paciente do encontro;
- `Encounter` aberto;
- `MedicationDispenseItem` existente e acessível;
- dispensação ligada a `MedicationRequest` do mesmo encontro;
- prescrição em estado compatível com administração conforme contrato RX vigente;
- requisição feita online.

A implementação deve revalidar essas condições no POST, dentro da operação de domínio; não confiar apenas no GET anterior.

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

Antes de suportar formalmente dose divergente como fluxo legítimo, a governança deve definir semântica, autorização e auditoria correspondentes. A UI v1 deve deixar claro que o fluxo suportado é confirmação de administração conforme o ato efetivamente realizado, sem oferecer mecanismo de ajuste terapêutico.

## Idempotência

`operation_key` é UUID única.

- primeiro POST válido cria a administração;
- retry com mesma chave reconhece o registro existente;
- mesma chave apontando para entrada incompatível gera conflito seguro;
- refresh/double-click não pode produzir administração duplicada.

## Rastreabilidade

A administração deve permitir reconstruir:

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
- Background Sync não confirma administração.

## Auditoria e evento

Após commit bem-sucedido:

- alteração fica auditável;
- emitir `nursing.medication.administered` com IDs técnicos e timestamp;
- não incluir nome do paciente, dose, unidade, medicamento, lote textual ou instrução clínica no evento genérico.

## Erros seguros

- fora de escopo: 404/negação sem PHI;
- encontro fechado: conflito seguro;
- dispense item incompatível: conflito/404 sem detalhes de outro paciente;
- operation key conflitante: conflito idempotente;
- indisponibilidade de rede: nenhuma confirmação local.

## Gates futuros

Exigem revisão clínica/operacional antes de implementação:

- recusa/omissão;
- atraso;
- administração parcial;
- dose divergente e respectiva justificativa;
- checagens de horário/janela de administração;
- identificação por código de barras;
- checagens automáticas de “certos” de medicação;
- administração de medicamento trazido pelo paciente ou fora do estoque/dispensação AegisShare;
- qualquer administração offline.
