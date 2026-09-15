# Spec 004 — Enfermagem

> Prioridade: P0  
> Dependências: Spec 001 — PEP; Spec 002 — ADT; Spec 003 — Prescrição/Farmácia; Spec 014 — PWA  
> Status: proposta — aguardando aprovação do mantenedor; implementação clínica ainda não liberada

## Contexto

A Spec 004 define o primeiro recorte de Enfermagem do AegisShare HIS. O escopo inicial é deliberadamente pequeno: **registro estruturado de sinais vitais/antropometria** e **administração de medicamento à beira do leito**. Evolução de enfermagem livre, SAE completa, escalas, balanço hídrico, dispositivos, curativos e planos de cuidado ficam fora deste ciclo.

O módulo reutiliza `Patient` e `Encounter` canônicos do PEP, o contexto operacional do ADT e a prescrição/dispensação da Spec 003. Não cria cadastro paralelo de paciente, atendimento, medicamento, lote ou prescrição.

A Spec 003 já depende de uma futura fonte estruturada de peso para regras de dose. Esta spec pode fornecer o fato estruturado `weight_kg`, mas **não autoriza automaticamente seu uso em decisão medicamentosa**: a política institucional de atualidade máxima, origem aceitável e demais critérios de validade clínica do peso continuam como gate de governança. Até esse gate fechar, regras RX dependentes de peso permanecem `NOT_EVALUABLE`.

A Spec 014 recomenda sinais vitais como primeiro piloto offline. Portanto esta spec define um piloto restrito e idempotente para **criação append-only de sinais vitais**, usando a fila local cifrada já existente. Administração de medicamento permanece `network-only`.

## User Stories

- Como profissional de enfermagem autorizado, quero registrar sinais vitais em um encontro acessível para manter o prontuário estruturado e rastreável.
- Como profissional de enfermagem autorizado, quero registrar sinais vitais mesmo durante uma perda temporária de conexão, sem duplicar ou sobrescrever dados quando a conexão voltar.
- Como profissional autorizado, quero consultar o histórico de sinais vitais sem permitir edição destrutiva de registros clínicos anteriores.
- Como profissional de enfermagem autorizado, quero confirmar a administração de um item prescrito e dispensado, preservando o vínculo com prescrição e lote.
- Como auditor, quero reconstruir quem registrou sinais vitais e quem administrou um medicamento, quando e em qual encontro, sem copiar PHI para logs técnicos.

## Requisitos Funcionais

- **RF-NUR-01 — Escopo canônico.** Todo registro pertence a um `Encounter` canônico do PEP. A UI não duplica nome, CPF ou dados demográficos como fonte de verdade.
- **RF-NUR-02 — Sinais vitais estruturados.** Registrar, de forma opcional e estruturada, temperatura, frequência cardíaca, frequência respiratória, pressão arterial sistólica/diastólica, saturação periférica de oxigênio e peso. Pelo menos uma medida deve ser informada.
- **RF-NUR-03 — Unidade explícita e sem inferência clínica.** As unidades canônicas desta versão são parte do contrato de persistência (`°C`, `bpm`, `irpm`, `mmHg`, `%`, `kg`). O sistema não converte unidades, não calcula referência normal/anormal e não produz recomendação clínica sem contrato posterior aprovado.
- **RF-NUR-04 — Tempo do fato.** Cada registro possui `recorded_at` (momento informado da aferição) e `created_at` (persistência no servidor). O servidor valida coerência temporal mínima e preserva ambos.
- **RF-NUR-05 — Histórico append-only.** Sinais vitais persistidos não são editados ou excluídos pela interface comum. Correção cria novo registro com vínculo `replaces`, preservando o original.
- **RF-NUR-06 — Piloto offline de sinais vitais.** O formulário de sinais vitais pode enfileirar somente a operação aprovada `nursing.vitals.record` quando offline. O payload local é cifrado pela infraestrutura da Spec 014, possui `idempotency_key` e contém somente IDs técnicos e medidas necessárias.
- **RF-NUR-07 — Sincronização segura.** Na reconexão, a sessão, permissão, escopo PEP e estado do encontro são revalidados no servidor. Reenvio da mesma `idempotency_key` não duplica o registro. Mudança incompatível de estado gera conflito explícito; não existe `last-write-wins`.
- **RF-NUR-08 — Fato de peso para integração futura.** `weight_kg` é um fato clínico estruturado com autor e horário. Um selector pode expor peso + proveniência técnica, mas o RX só poderá tratá-lo como elegível após aprovação da política de atualidade/origem pela governança clínica/farmacêutica.
- **RF-NUR-09 — Administração vinculada à prescrição.** Uma administração referencia um `MedicationDispenseItem` da Spec 003 e, por consequência, o item prescrito, medicamento e lote. A operação só é oferecida quando o encontro e a prescrição continuam acessíveis e o item possui dispensação rastreável.
- **RF-NUR-10 — Administração conservadora v1.** A primeira versão registra somente administração efetivamente confirmada. Dose e unidade administradas são valores estruturados informados/confirmados pelo profissional. O sistema não infere equivalência entre unidades e não implementa ajuste, substituição ou desvio de dose sem contrato clínico posterior.
- **RF-NUR-11 — Idempotência da administração.** Cada confirmação possui `operation_key` UUID única. Reenvio da mesma chave reconhece a operação existente e não cria dupla administração.
- **RF-NUR-12 — Administração online.** Administração de medicamento é `network-only`. Nenhuma confirmação é persistida em Cache Storage, IndexedDB ou Background Sync.
- **RF-NUR-13 — Autorização.** RBAC + ABAC deny-by-default: capacidades separadas para visualizar enfermagem, registrar sinais vitais e administrar medicamento. Todo acesso identificável exige também escopo PEP válido para o paciente; contexto ADT/local pode restringir adicionalmente quando configurado.
- **RF-NUR-14 — Auditoria e eventos.** Leituras sensíveis e mutações relevantes são auditadas. Eventos internos `nursing.vitals.recorded` e `nursing.medication.administered` levam apenas IDs técnicos, estado estritamente necessário e timestamp; não levam nome, CPF, texto clínico ou instrução medicamentosa.

## Requisitos Não Funcionais

- **RNF-NUR-01** PostgreSQL é a fonte de verdade para sinais vitais e administração concluída.
- **RNF-NUR-02** Registros clínicos persistidos são append-only pela interface comum e protegidos contra alteração destrutiva acidental.
- **RNF-NUR-03** Nenhuma API REST pública será criada; interação por views/forms Django server-rendered, HTMX quando útil e sincronização interna já contratada pela PWA.
- **RNF-NUR-04** Logs e eventos técnicos não contêm identificação direta do paciente nem valores clínicos quando não forem indispensáveis ao evento.
- **RNF-NUR-05** UI essencial cumpre WCAG 2.1 AA e funciona em desktop, tablet e smartphone.
- **RNF-NUR-06** Operações offline e administração são idempotentes e retornam conflitos seguros, sem stacktrace/SQL/PHI.
- **RNF-NUR-07** Migrações são reversíveis e não movem/destróem tabelas PEP, ADT ou RX existentes.
- **RNF-NUR-08** O piloto offline usa apenas a fila cifrada da Spec 014; nenhuma segunda infraestrutura offline é criada.

## Critérios de Aceitação

```gherkin
Cenário: registrar sinais vitais em encontro aberto
  Dado um profissional com capacidade de registrar sinais vitais e acesso PEP ao paciente
  E um encontro aberto
  Quando ele informa pelo menos uma medida válida e confirma o registro
  Então um registro append-only é persistido no encontro canônico
  E autor, recorded_at e created_at ficam rastreáveis
  E o evento nursing.vitals.recorded é agendado após commit sem PHI textual
```

```gherkin
Cenário: corrigir sinais vitais sem apagar histórico
  Dado um registro de sinais vitais já persistido
  Quando um profissional autorizado registra uma correção
  Então um novo registro é criado com vínculo replaces
  E o registro original permanece inalterado
```

```gherkin
Cenário: registrar sinais vitais offline e sincronizar uma única vez
  Dado o PWA instalado e uma sessão autenticada válida
  E um encontro aberto acessível
  Quando a conexão cai e o profissional confirma sinais vitais
  Então somente um envelope cifrado nursing.vitals.record é armazenado localmente
  E quando a conexão volta a operação é revalidada no servidor
  E múltiplos reenvios da mesma idempotency_key resultam em um único registro clínico
```

```gherkin
Cenário: encontro fecha antes da sincronização offline
  Dado sinais vitais enfileirados enquanto o encontro estava aberto
  E o encontro foi encerrado antes da sincronização
  Quando o dispositivo tenta sincronizar
  Então o servidor não insere silenciosamente o registro
  E devolve conflito seguro para revisão manual
  E o conflito é auditável sem PHI em logs técnicos
```

```gherkin
Cenário: peso estruturado não ativa regra de dose sem política aprovada
  Dado um registro de enfermagem com weight_kg
  E a política institucional de atualidade/origem do peso ainda não aprovada
  Quando o RX avalia uma regra dependente de peso
  Então o peso não é consumido automaticamente como fato elegível
  E a checagem continua NOT_EVALUABLE
```

```gherkin
Cenário: administração mantém rastreabilidade até o lote
  Dado um item prescrito validado e um MedicationDispenseItem rastreável
  E um profissional com capacidade de administrar e acesso PEP
  Quando ele confirma online a administração com operation_key inédita
  Então uma única MedicationAdministration é persistida
  E é possível reconstruir administração -> dispensação -> lote -> item prescrito -> encontro
```

```gherkin
Cenário: administração não é enfileirada offline
  Dado o PWA instalado
  Quando a conexão cai antes da confirmação da administração
  Então o POST não é confirmado
  E nenhuma administração é gravada no Cache Storage ou IndexedDB
```

```gherkin
Cenário: usuário sem escopo PEP tenta acessar enfermagem
  Dado um encontro pertencente a paciente fora do escopo do usuário
  Quando ele tenta abrir sinais vitais ou medicações
  Então o sistema nega sem revelar identificação, valores clínicos ou medicamentos
```

## Telas e Fluxos

- `clinical/nursing/worklist.html` — encontros acessíveis conforme capacidade e escopo.
- `clinical/nursing/encounter.html` — resumo de enfermagem do encontro e histórico de sinais vitais.
- `clinical/nursing/vitals_form.html` — novo registro/correção de sinais vitais.
- `clinical/nursing/medications.html` — itens dispensados elegíveis para administração no encontro.
- `clinical/nursing/medication_administer.html` — confirmação online de administração.

## Fora de Escopo

- SAE completa, diagnósticos e prescrições de enfermagem;
- evolução/anotação livre de enfermagem;
- escalas clínicas e escores;
- balanço hídrico;
- dispositivos, curativos e procedimentos;
- faixas de normalidade, alarmes ou recomendações automáticas de sinais vitais;
- conversão automática de unidades;
- administração de medicamento sem vínculo rastreável com a dispensação da Spec 003;
- registro offline de administração de medicamento;
- alteração de prescrição, dispensação ou estoque;
- faturamento e cobrança;
- integração externa por REST/FHIR.

## Dependências e Gates Clínicos

1. `Patient` e `Encounter` pertencem à Spec 001.
2. Local/leito/internação pertencem à Spec 002 e são apenas contexto operacional.
3. Prescrição, dispensação e lote pertencem à Spec 003.
4. A infraestrutura offline cifrada pertence à Spec 014; esta spec aprova apenas o tipo de operação `nursing.vitals.record`.
5. **Peso para RX:** registrar `weight_kg` não fecha sozinho T-RX-17/T-RX-02. A governança clínica/farmacêutica deve aprovar origem aceitável e janela de atualidade antes do consumo automático pelo safety engine.
6. **Exceções de administração:** omissão, recusa, atraso, dose divergente, substituição e demais estados não são inventados nesta versão; exigem política institucional e revisão desta spec.

## Riscos

- associação de sinais vitais ao encontro/paciente errado;
- duplicação de registro após reconexão;
- sincronização tardia em encontro já encerrado;
- exposição de valores clínicos no armazenamento local ou logs;
- uso de peso desatualizado em decisão medicamentosa;
- dupla administração por retry;
- perda de rastreabilidade entre administração e lote;
- tentativa de administrar item de paciente fora do escopo;
- interpretação automática de sinais vitais sem referência aprovada.

## Rastreabilidade inicial

| Requisito | Superfície prevista | Teste previsto |
|---|---|---|
| RF-NUR-01/02/03/04 | encontro + formulário de sinais vitais | model + form + view |
| RF-NUR-05 | correção por `replaces` | model/service + imutabilidade |
| RF-NUR-06/07 | fila PWA de sinais vitais | service + Playwright offline + idempotência |
| RF-NUR-08 | selector de peso com metadados | selector contract + gate RX |
| RF-NUR-09/10/11 | administração online | service + boundary + idempotência |
| RF-NUR-12 | formulário de administração | Playwright network-only |
| RF-NUR-13 | todas as rotas | RBAC + ABAC + negações sem PHI |
| RF-NUR-14 | services/eventos | audit + AsyncAPI contract |
