# Contrato interno — selector de peso

## Objetivo

Expor o fato estruturado de peso mais recente registrado pela Enfermagem, com proveniência técnica suficiente para uma futura política de elegibilidade clínica.

Este contrato **não aprova** o uso automático do peso em decisão medicamentosa. O gate T-NUR-09 permanece obrigatório antes de qualquer integração com o safety engine da Spec 003.

## Interface

```python
latest_weight_fact(*, encounter=None, patient=None)
```

Exatamente um escopo deve ser informado:

- `encounter`: busca apenas naquele encontro;
- `patient`: busca entre os encontros canônicos daquele paciente.

Informar ambos ou nenhum é erro de uso do selector.

## Resultado

Quando não existe peso no escopo, retorna `None`.

Quando existe, retorna o fato com os seguintes campos:

```text
weight_kg
recorded_at
record_id
recorded_by_id
encounter_id
origin
```

`origin` preserva o metadado técnico `ONLINE` ou `OFFLINE_SYNC` do `VitalSignsRecord`.

## Ordenação

O fato mais recente é definido por `recorded_at`, com `created_at` apenas como desempate técnico. Um sync tardio não transforma uma aferição antiga no peso clinicamente mais recente apenas porque foi persistida depois.

Registros sem `weight_kg` não substituem um fato de peso anterior para fins deste selector.

## Limites clínicos deliberados

O selector não:

- aplica janela máxima de idade do peso;
- aceita ou rejeita uma origem;
- decide se um peso de outro encontro pode ser reutilizado;
- classifica o fato como válido, atual, confiável ou elegível;
- converte unidade;
- calcula dose;
- altera o comportamento do RX.

Essas decisões pertencem ao T-NUR-09 e exigem aprovação de governança clínica/farmacêutica. Até lá, regras RX dependentes de peso continuam `NOT_EVALUABLE`, mesmo quando `latest_weight_fact()` encontra um valor estruturado.
