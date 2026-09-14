# Spec 003 — Prescrição e Farmácia

> Prioridade: P0  
> Dependências: Spec 001 — PEP; Spec 002 — ADT  
> Status: aprovada pelo mantenedor em 2026-09-14 — implementação incremental liberada

## Contexto

O módulo de Prescrição e Farmácia controla a prescrição medicamentosa vinculada ao prontuário, a validação farmacêutica, a dispensação e a rastreabilidade de estoque farmacêutico por lote e validade. A superfície permanece integralmente dentro do monólito Django, renderizada no servidor, sem API REST pública.

O módulo reutiliza `Patient` e `Encounter` canônicos do PEP e não cria um segundo cadastro de paciente ou atendimento. O ADT é usado apenas como contexto operacional quando houver internação; uma prescrição continua vinculada ao `Encounter`, não a uma cópia de admissão.

O SDD exige checagem de alergias/interações e dose por peso/idade. O repositório atual possui idade calculável por `Patient.birth_date`, mas **ainda não possui fonte estruturada aprovada para alergias nem peso clínico atual**. Portanto esta spec define os contratos e o comportamento fail-safe, mas proíbe alegar “sem alergia”, calcular dose por peso ou liberar uma regra clínica automática sem fonte e referência clínica previamente aprovadas. O módulo pode registrar que a revisão foi necessária/realizada, mas não inventa fatos clínicos ausentes.

## User Stories

- Como prescritor autorizado, quero registrar uma prescrição em um encontro aberto para documentar a terapia proposta com rastreabilidade.
- Como farmacêutico autorizado, quero revisar alertas e validar uma prescrição antes da dispensação.
- Como farmacêutico autorizado, quero dispensar por lote e validade sem permitir estoque negativo ou perda da rastreabilidade.
- Como profissional assistencial autorizado, quero visualizar o histórico de prescrições e dispensações do encontro sem permitir edição destrutiva de registros concluídos.
- Como auditor, quero reconstruir criação, validação, alertas, dispensação e ajustes sem copiar conteúdo clínico sensível para logs técnicos.

## Requisitos Funcionais

- **RF-RX-01 — Catálogo de medicamentos.** Manter `Drug` com identificação interna, nome genérico/apresentação, unidade de dispensação, status ativo e metadados necessários ao uso interno. Alterações clínicas de referência são auditadas.
- **RF-RX-02 — Prescrição vinculada ao PEP.** Criar `MedicationRequest` para um `Encounter` canônico acessível e aberto, com autor, data/hora, status e itens de prescrição. A prescrição não duplica nome, CPF ou dados demográficos do paciente.
- **RF-RX-03 — Itens estruturados.** Cada item de prescrição registra medicamento, dose, unidade, via, frequência/instrução, duração quando aplicável e observação clínica mínima. Campos obrigatórios são validados no servidor.
- **RF-RX-04 — Histórico imutável.** Prescrições submetidas/validadas e dispensações concluídas não podem ser editadas ou excluídas pela interface comum. Correções posteriores usam cancelamento/adendo/novo registro rastreável, sem sobrescrever o original.
- **RF-RX-05 — Interações medicamentosas.** Antes da validação farmacêutica, o sistema compara os itens da prescrição com a base `Interaction` ativa. A severidade, mensagem e natureza bloqueante são dados de referência governados; o código não inventa limiares clínicos. Alertas bloqueantes impedem validação até resolução compatível com a política aprovada.
- **RF-RX-06 — Alergias.** A tela de validação deve exibir a situação da checagem de alergias. Quando existir uma fonte estruturada PEP aprovada, ela será usada automaticamente. Enquanto essa fonte não existir, o sistema deve declarar a checagem automática indisponível e exigir revisão explícita do profissional; nunca deve inferir “sem alergias conhecidas”.
- **RF-RX-07 — Dose por idade/peso com fail-safe.** Regras de dose só podem ser avaliadas a partir de `DoseRule`/referência clínica aprovada. Idade pode ser derivada de `birth_date`; peso só pode vir de fonte clínica estruturada aprovada. Se uma regra exigir dado ausente, o sistema sinaliza “não validável automaticamente” e não fabrica valor nem converte isso em aprovação silenciosa.
- **RF-RX-08 — Validação farmacêutica.** Usuário com capacidade de validação revisa itens e alertas e registra decisão, profissional e horário. A validação não equivale à assinatura eletrônica jurídica do PEP T-PEP-08, que permanece fora desta spec até aprovação própria.
- **RF-RX-09 — Estoque farmacêutico.** `StockItem` e `Lot` controlam saldo farmacêutico rastreável por medicamento, lote e validade. Lotes expirados, inativos ou sem saldo não podem ser dispensados.
- **RF-RX-10 — Dispensação transacional.** `MedicationDispense` consome estoque por lote dentro de `transaction.atomic()`, com locking/constraint suficiente para impedir saldo negativo sob concorrência. A mesma `operation_key` não pode duplicar a dispensação.
- **RF-RX-11 — Rastreabilidade por lote.** Cada item dispensado referencia o lote efetivamente usado, quantidade, profissional e horário, permitindo reconstruir medicamento → lote → prescrição → encontro.
- **RF-RX-12 — Autorização.** RBAC + ABAC deny-by-default: capacidades separadas para prescrever, validar, dispensar, manter catálogo/estoque e visualizar; qualquer acesso identificável exige também escopo PEP válido para o paciente.
- **RF-RX-13 — Auditoria e eventos.** Leituras sensíveis e mutações relevantes são auditadas. Eventos internos `prescription.created`, `prescription.validated`, `medication.dispensed` e `stock.low` carregam apenas IDs técnicos, estado e timestamp necessários; não carregam nome, CPF, texto de prescrição ou alergia.
- **RF-RX-14 — PWA.** Criação/validação de prescrição e dispensação permanecem `network-only` nesta versão. Nenhuma mutação farmacêutica será enfileirada offline sem contrato clínico específico aprovado.

## Requisitos Não Funcionais

- **RNF-RX-01** PostgreSQL é a fonte de verdade para prescrição, validação, lote e saldo.
- **RNF-RX-02** Toda mutação de estoque usa transação atômica e deve ser segura sob concorrência.
- **RNF-RX-03** Nenhuma rota REST pública será adicionada; interação por Django views/forms/HTMX/WebSocket interno autenticados por sessão.
- **RNF-RX-04** Logs/auditoria genérica/eventos técnicos não devem conter texto livre de prescrição, alergia, motivo clínico ou identificação direta do paciente.
- **RNF-RX-05** A UI essencial deve cumprir WCAG 2.1 AA e funcionar em desktop, tablet e smartphone.
- **RNF-RX-06** Catálogo de interações e regras de dose deve possuir procedência/versão/estado de aprovação; o sistema não deve gerar recomendação clínica a partir de referência não aprovada.
- **RNF-RX-07** Migrações devem ser reversíveis e não mover/destruir tabelas PEP/ADT existentes.
- **RNF-RX-08** Operações críticas de dispensação devem ser idempotentes e produzir erro operacional seguro, sem SQL/stacktrace, em caso de conflito.

## Critérios de Aceitação

```gherkin
Cenário: prescritor registra prescrição em encontro aberto
  Dado um profissional com capacidade de prescrever e acesso PEP ao paciente
  E um encontro aberto
  Quando ele registra uma prescrição com itens válidos
  Então a prescrição é persistida vinculada ao encontro canônico
  E o histórico registra autor e horário
  E um evento prescription.created é agendado após commit sem PHI textual
```

```gherkin
Cenário: interação bloqueante impede validação
  Dado uma prescrição submetida com dois medicamentos
  E uma interação ativa, aprovada e marcada como bloqueante entre eles
  Quando o farmacêutico tenta validar a prescrição
  Então a validação é recusada
  E o alerta exibe a referência clínica configurada
  E nenhum limiar adicional é inferido pelo código
```

```gherkin
Cenário: ausência de fonte estruturada de alergia não vira falso negativo
  Dado um paciente cuja fonte estruturada de alergias ainda não está disponível
  Quando o farmacêutico abre a validação
  Então a tela informa que a checagem automática de alergias está indisponível
  E não exibe a afirmação “sem alergias conhecidas”
  E exige revisão explícita antes da decisão farmacêutica conforme política institucional
```

```gherkin
Cenário: regra de dose exige peso ausente
  Dado uma regra de dose aprovada que depende do peso
  E nenhuma fonte clínica estruturada de peso disponível para o encontro
  Quando o sistema executa a checagem de dose
  Então o item é marcado como não validável automaticamente
  E nenhum peso ou dose é estimado pelo sistema
```

```gherkin
Cenário: dispensação por lote é atômica
  Dado uma prescrição validada
  E um lote ativo, não expirado e com saldo suficiente
  Quando um farmacêutico autorizado confirma a dispensação
  Então a dispensação referencia o lote utilizado
  E o saldo é reduzido na mesma transação
  E a auditoria registra a operação
  E o evento medication.dispensed é emitido somente após commit
```

```gherkin
Cenário: duas dispensações concorrem pelo último saldo
  Dado um lote com saldo suficiente para apenas uma das duas operações concorrentes
  Quando dois profissionais tentam dispensar simultaneamente
  Então apenas uma operação confirma o consumo
  E a outra recebe conflito seguro
  E o saldo nunca fica negativo
```

```gherkin
Cenário: profissional sem escopo PEP tenta abrir prescrição
  Dado uma prescrição pertencente a paciente fora do escopo do usuário
  Quando ele tenta acessar a tela
  Então o sistema nega sem revelar medicamento, prescrição ou identificação do paciente
```

```gherkin
Cenário: dispensação não funciona offline
  Dado o PWA instalado
  Quando a conexão é interrompida antes de confirmar a dispensação
  Então o POST falha por ausência de rede
  E nenhuma dispensação é armazenada no Cache Storage ou IndexedDB offline
```

## Telas e Fluxos

- `clinical/prescription/prescription_list.html` — prescrições conforme escopo e capacidade.
- `clinical/prescription/new.html` — criação de prescrição e itens.
- `clinical/prescription/detail.html` — histórico, itens e estado.
- `clinical/prescription/validate.html` — revisão farmacêutica, interações e estado da checagem de alergias/dose.
- `clinical/prescription/dispense.html` — seleção de lote/quantidade e confirmação de dispensação.
- `clinical/prescription/dispense_list.html` — histórico de dispensações autorizadas.
- `clinical/prescription/drug_catalog.html` — catálogo interno.
- `clinical/prescription/pharmacy_stock.html` — estoque/lotes farmacêuticos.

## Fora de Escopo

- administração do medicamento à beira do leito (Spec 004 — Enfermagem);
- compras/fornecedores e estoque geral hospitalar (Spec 009);
- assinatura eletrônica/ICP-Brasil até fechamento de T-PEP-08;
- algoritmos de dose, contraindicação ou interação sem referência clínica institucional aprovada;
- cadastro duplicado de alergias dentro do app de prescrição;
- integração externa por REST/FHIR;
- dispensação/prescrição offline;
- faturamento da medicação.

## Dependências e Gates Clínicos

1. `Patient`/`Encounter` e autorização PEP são reutilizados da Spec 001.
2. Contexto de internação pode ser consultado no ADT, mas o vínculo clínico primário permanece o `Encounter`.
3. **Alergia estruturada:** o PEP atual ainda não implementa `AllergyIntolerance`; a automação de alergia fica bloqueada até uma extensão de Spec 001 aprovada. A UI deve falhar de forma explícita, não otimista.
4. **Peso clínico:** não há fonte estruturada aprovada hoje; regras dependentes de peso ficam não validáveis até a Spec 004 ou outra fonte clínica aprovada fornecer esse fato.
5. **Conteúdo de `Interaction` e `DoseRule`:** exige governança clínica/farmacêutica, procedência e versionamento; os testes podem usar referências sintéticas, nunca regras terapêuticas reais inventadas no código.

## Riscos

- prescrição para paciente/encontro errado;
- falso negativo de alergia por ausência de dados;
- automatização de dose sem peso/referência válida;
- alerta excessivo ou insuficiente por base de interação sem governança;
- dupla dispensação/estoque negativo por concorrência;
- uso de lote expirado;
- exposição de medicação em auditlog, eventos, URLs ou respostas de negação;
- confusão entre validação farmacêutica e assinatura clínica jurídica;
- tentativa de dispensação com estado de estoque obsoleto/offline.

## Rastreabilidade inicial

| Requisito | Rota/View prevista | Template | Teste previsto |
|---|---|---|---|
| RF-RX-01 | `/medicamentos/` | `drug_catalog.html` | model + view + authorization |
| RF-RX-02/03/04 | `/prescricoes/`, `/prescricoes/nova/`, `/prescricoes/<uuid>/` | list/new/detail | model + form + view + append-only |
| RF-RX-05/06/07/08 | `/prescricoes/<uuid>/validar/` | `validate.html` | safety-review + missing-data + authorization |
| RF-RX-09/11 | `/estoque-farmacia/` | `pharmacy_stock.html` | model + lot/expiry + authorization |
| RF-RX-10 | `/prescricoes/<uuid>/dispensar/` | `dispense.html` | service + idempotency + PostgreSQL concurrency |
| RF-RX-12 | todas as rotas | todas | RBAC + ABAC boundary tests |
| RF-RX-13 | services/eventos | — | audit + AsyncAPI contract tests |
| RF-RX-14 | rotas mutáveis | — | Playwright PWA network-only |
