# Contrato de Segurança Medicamentosa — Spec 003

## Objetivo

Definir como o sistema executa checagens estruturais de segurança sem transformar o código-fonte em fonte de verdade clínica. Este contrato não contém regras terapêuticas reais; ele define estados, entradas, saídas e comportamento fail-safe.

## Princípios

1. referência clínica real exige procedência, versão e aprovação;
2. dado clínico ausente é `UNKNOWN`/`UNAVAILABLE`, nunca valor negativo inferido;
3. alerta bloqueante configurado não possui override genérico nesta primeira versão;
4. código não deduz `blocking` a partir de severidade;
5. nenhum cálculo usa `eval`, scripts ou expressões arbitrárias armazenadas no banco;
6. resultado automático sempre informa qual versão de referência foi usada;
7. checagem automática auxilia o profissional e não substitui validação clínica/farmacêutica.

## Entrada canônica

O safety engine recebe apenas objetos já autorizados e dados estruturados:

```text
MedicationRequest SUBMITTED
MedicationRequestItem[]
Patient.birth_date
structured_allergies: coleção autorizada OU UNAVAILABLE
weight_fact: valor estruturado + timestamp + origem aprovada OU UNAVAILABLE
Interaction[] ativas/aprovadas
DoseRule[] ativas/aprovadas
reference_set_version
```

Não recebe HTML, request bruto, logs nem texto de evolução como fonte de alergia/peso.

## Saída canônica

```text
SafetyResult
  allergy_status
  interaction_status
  dose_status
  findings[]
  blocking_count
  warning_count
  reference_set_version
```

Estados:

### allergy_status

- `UNAVAILABLE` — não existe fonte estruturada aprovada;
- `REVIEW_REQUIRED` — fonte/revisão exige ação profissional;
- `REVIEW_CONFIRMED` — profissional confirmou revisão manual quando permitida;
- `STRUCTURED_CHECKED` — fonte estruturada aprovada foi efetivamente consultada.

Nenhum desses estados significa, sozinho, “paciente não possui alergias”. A eventual fonte PEP deve distinguir explicitamente alergia conhecida, ausência documentada e desconhecido.

### interaction_status

- `PASS` — nenhuma interação ativa correspondente foi encontrada no conjunto de referência usado;
- `WARNING` — há achado não bloqueante;
- `BLOCKED` — há pelo menos um `Interaction.blocking=True`.

### dose_status

- `PASS` — todas as regras aplicáveis e avaliáveis ficaram dentro dos limites estruturados;
- `WARNING` — regra não bloqueante gerou observação configurada;
- `BLOCKED` — regra aprovada/bloqueante não foi satisfeita;
- `NOT_EVALUABLE` — regra aplicável requer fato clínico ausente ou unidade não suportada.

A política que determina se `NOT_EVALUABLE` impede validação em produção deve ser aprovada pela governança antes de ativar regras reais dependentes desse fato.

## Interações

Algoritmo permitido:

1. obter IDs únicos de `Drug` dos itens;
2. formar pares canônicos sem ordem;
3. consultar `Interaction(active=True)` para esses pares e versão aprovada;
4. gerar um finding por referência encontrada;
5. `blocking` do finding é copiado da referência, não calculado;
6. nenhum achado encontrado resulta em `PASS` **somente em relação ao conjunto de referência consultado**.

A UI deve mostrar a fonte/versão da referência, sem sugerir cobertura além da base carregada.

## Alergias

Enquanto `AllergyIntolerance` estruturado não existir no PEP:

```text
structured_allergies = UNAVAILABLE
allergy_status = UNAVAILABLE
```

Comportamento obrigatório:

- não executar busca textual em evolução/prontuário;
- não interpretar coleção ausente como vazia;
- não renderizar “sem alergias conhecidas”;
- mostrar limitação ao validador;
- se a política institucional permitir revisão manual, registrar somente o fato de que a revisão foi confirmada, por quem e quando, não inventar um registro de alergia.

Quando a extensão PEP for aprovada, este contrato deve ser revisado para mapear os estados estruturados sem duplicar a entidade no app de prescrição.

## Dose por idade

Idade é derivada de `Patient.birth_date` e da data/hora clínica da prescrição/encontro, usando cálculo determinístico em dias/anos conforme `DoseRule`.

O sistema não carrega faixas etárias terapêuticas no código. Os limites vêm da regra aprovada.

## Dose por peso

`weight_fact` deve conter:

```text
value_kg
observed_at
source_object_id
source_type aprovado
```

Regras:

- peso não é digitado novamente no formulário de prescrição para alimentar decisão automática;
- peso sem origem estruturada aprovada é ignorado para automação;
- se a regra exige peso e não existe `weight_fact` válido, retornar `NOT_EVALUABLE`;
- o contrato de atualidade máxima do peso deve ser definido pela governança clínica/Spec 004 antes de ativar regra real; o código não inventa uma janela temporal.

## Unidades

Inicialmente somente comparação quando `MedicationRequestItem.dose_unit` e `DoseRule.dose_unit` são diretamente compatíveis pela tabela de unidades aprovada.

- sem conversão implícita;
- sem heurística por string;
- conversões futuras exigem tabela versionada e testes.

## Persistência da revisão

A tentativa de validação persiste `MedicationSafetyReview` e `MedicationSafetyFinding` suficientes para identificar:

- profissional;
- horário;
- versão de referência;
- tipo/severidade/bloqueio;
- referências técnicas (`Interaction`/`DoseRule`/futura alergia PEP).

Não persistir cópias desnecessárias de nome do paciente, CPF ou texto livre clínico no finding.

## Testes obrigatórios

- par de interação sintética não bloqueante → `WARNING`;
- par sintético `blocking=True` → `BLOCKED`;
- severidade alta com `blocking=False` continua não bloqueante, provando que o código não infere política;
- alergia estruturada indisponível → `UNAVAILABLE`, nunca `PASS`;
- regra por idade com fato disponível → avaliação determinística;
- regra por peso sem peso aprovado → `NOT_EVALUABLE`;
- unidade incompatível → `NOT_EVALUABLE`/erro seguro, nunca conversão heurística;
- mudança de versão de referência não altera retrospectivamente `MedicationSafetyReview` já gravado.
