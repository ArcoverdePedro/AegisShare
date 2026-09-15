# Extensão da Spec 001 — AllergyIntolerance estruturada

**Status:** definida para integração futura; implementação não autorizada por este documento isoladamente.  
**Módulo pai:** 001 — PEP  
**Consumidor inicial:** 003 — Prescrição e Farmácia

## Contexto

A Spec 003 precisa de uma fonte estruturada e auditável de alergias/intolerâncias para habilitar checagem automática. Até esta extensão ser implementada e validada, o módulo de prescrição deve continuar exibindo `automatic allergy check unavailable`/equivalente em pt-BR, exigir revisão manual explícita quando aplicável e nunca inferir “sem alergias conhecidas”.

Esta extensão define o contrato da fonte. Ela não adiciona conteúdo clínico de referência nem autoriza automação terapêutica por si só.

## User Stories

- Como profissional assistencial autorizado, quero registrar uma alergia/intolerância estruturada no PEP para que o histórico clínico não dependa somente de texto livre.
- Como farmacêutico autorizado, quero que a validação de prescrição consulte somente registros estruturados, vigentes e verificáveis para evitar falsos negativos.
- Como auditor, quero saber quem registrou, alterou o estado clínico e invalidou um registro, preservando o histórico.

## Requisitos Funcionais

### RF-ALLERGY-01 — Registro estruturado

Cada registro deve pertencer a um `Patient` e conter, no mínimo:

- substância/referência estruturada ou identificador institucional governado;
- descrição legível;
- `clinical_status`;
- `verification_status`;
- criticidade quando conhecida;
- autor e timestamp do registro;
- origem/fonte do dado.

### RF-ALLERGY-02 — Sem exclusão silenciosa

Registros utilizados clinicamente não devem ser apagados para “corrigir” histórico. Correções devem usar estado apropriado, nova versão/registro ou mecanismo auditável equivalente.

### RF-ALLERGY-03 — Fonte válida para automação

A checagem automática da Spec 003 só pode considerar um registro como fonte clínica quando a política aprovada declarar explicitamente a combinação de estados elegível. Até essa política ser validada, o safety engine deve tratar a fonte como indisponível/revisão manual requerida.

### RF-ALLERGY-04 — Ausência não é negativa clínica

A ausência de registros estruturados não pode ser exibida como “paciente sem alergias”. O estado deve diferenciar:

- fonte ainda não revisada/indisponível;
- revisão realizada sem registro ativo, quando houver workflow aprovado;
- registros ativos/verificados;
- registros invalidados/entered-in-error.

### RF-ALLERGY-05 — Escopo PEP

Toda leitura ou mutação identificável deve exigir sessão, capacidade explícita e `can_access_patient(user, patient)`.

### RF-ALLERGY-06 — Auditoria

Criação, alteração de estado e leitura identificável devem ser auditáveis sem copiar reação/descrição clínica livre para logs técnicos ou eventos.

## Requisitos Não Funcionais

- Sem API REST pública.
- Server-rendered/HTMX quando houver UI.
- `Cache-Control: private, no-store, max-age=0` nas superfícies clínicas.
- Nenhum dado de alergia em Cache Storage, push notification, log técnico ou evento interno não minimizado.
- Migração reversível e histórico preservado.

## Modelo de Dados Proposto

`AllergyIntolerance`:

```text
id: UUID
patient: FK Patient
substance_code: string governada
substance_text: string legível
clinical_status: ACTIVE | INACTIVE | RESOLVED
verification_status: UNCONFIRMED | CONFIRMED | ENTERED_IN_ERROR
criticality: LOW | HIGH | UNABLE_TO_ASSESS | blank
reaction_text: texto clínico opcional, sensível
onset_at: datetime opcional
recorded_by: FK User
recorded_at: datetime
source: string governada
source_version: string opcional
created_at / updated_at
```

O modelo final pode refinar enumerações antes da implementação, desde que preserve os estados semânticos necessários para não confundir “ausência de dado” com “negação clínica”.

## Telas e Fluxos Propostos

Nenhuma nova rota é publicada neste incremento. Quando aprovada para implementação, a extensão deve atualizar previamente `contracts/routes.md` e `contracts/forms.md` da Spec 001.

Fluxo futuro mínimo:

1. profissional abre paciente autorizado;
2. registra/atualiza estado de AllergyIntolerance;
3. PEP audita a mutação;
4. Spec 003 consulta somente a interface interna/selector aprovado;
5. safety review registra qual versão/estado da fonte foi utilizada.

## Contrato com a Spec 003

A integração futura deve expor uma função Python interna, não endpoint público, com semântica equivalente a:

```python
get_structured_allergy_context(*, patient, actor) -> AllergyContext
```

O retorno deve distinguir explicitamente `AVAILABLE`, `REVIEW_REQUIRED` e `UNAVAILABLE`, além dos registros elegíveis. O módulo de prescrição não deve consultar tabelas de alergia por heurística própria nem interpretar texto livre como dado estruturado.

## Critérios de Aceitação

```gherkin
Cenário: ausência da fonte estruturada não vira falso negativo
  Dado que a extensão ainda não está implementada ou revisada
  Quando a validação farmacêutica é executada
  Então o sistema informa que a checagem automática de alergias está indisponível
  E não informa “sem alergias conhecidas”
  E exige a política de revisão manual definida pela Spec 003
```

```gherkin
Cenário: paciente fora do escopo não revela alergias
  Dado um usuário autenticado sem acesso PEP ao paciente
  Quando tenta consultar uma futura superfície de AllergyIntolerance
  Então o sistema nega/oculta a existência do registro sem expor PHI
```

## Fora de Escopo deste incremento

- implementar o model/migração;
- publicar tela/rota;
- importar terminologia clínica externa;
- decidir quais substâncias, códigos ou ontologias institucionais são oficiais;
- habilitar checagem automática na Spec 003;
- afirmar juridicamente que uma lista vazia equivale a ausência de alergia.

## Dependências e Gates

- validação clínica/farmacêutica da política de estados elegíveis;
- definição institucional da terminologia de substâncias;
- revisão LGPD/auditoria antes de qualquer cache/offline;
- atualização explícita da Spec 003 antes de remover o gate manual.

## Rastreabilidade

| Requisito | Integração atual | Teste atual |
|---|---|---|
| RF-ALLERGY-04 | Spec 003 mantém fonte `UNAVAILABLE` e revisão manual explícita | `test_manual_allergy_review_is_required_without_structured_source` |
| RF-ALLERGY-05 | futuro selector PEP + `can_access_patient` | pendente da implementação da extensão |
| RF-ALLERGY-06 | contrato de minimização existente em PEP/RX | pendente da implementação da extensão |
