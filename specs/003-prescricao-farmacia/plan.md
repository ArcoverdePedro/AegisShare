# Plano Técnico — Spec 003 Prescrição e Farmácia

## Arquitetura

Criar `apps/clinical/prescription` como bounded context dentro do monólito. O app referencia `apps.clinical.pep.models.Patient`/`Encounter` por relações explícitas e não replica identidade do paciente. Contexto ADT pode ser consultado por selector quando necessário, sem transformar `Admission` em fonte clínica da prescrição.

Estrutura prevista:

```text
apps/clinical/prescription/
  models.py
  forms.py
  selectors.py
  services.py
  safety.py
  events.py
  permissions.py
  views.py
  urls.py
  migrations/
  tests/
templates/clinical/prescription/
```

Nenhuma API REST pública será criada.

## Modelo de Dados

Detalhado em `data-model.md`. Entidades previstas:

- `Drug`: catálogo interno de medicamentos;
- `Interaction`: relação governada entre dois medicamentos;
- `DoseRule`: regra de referência versionada, nunca lógica terapêutica hardcoded;
- `MedicationRequest`: cabeçalho da prescrição vinculada ao `Encounter`;
- `MedicationRequestItem`: item estruturado de medicamento/dose/via/frequência;
- `MedicationDispense`: ato idempotente de dispensação;
- `MedicationDispenseItem`: item dispensado e lote utilizado;
- `StockItem`: controle farmacêutico por medicamento;
- `Lot`: lote, validade e saldo atual;
- `StockMovement`: razão auditável de cada alteração de saldo.

O app não cria `AllergyIntolerance`: alergias pertencem ao PEP. Até existir fonte PEP estruturada aprovada, a checagem automática fica explicitamente indisponível e a decisão farmacêutica exige registro de revisão manual conforme política institucional.

## Estado e Imutabilidade

Fluxo inicial de `MedicationRequest`:

```text
DRAFT -> SUBMITTED -> VALIDATED
  |          |            |
  +------> CANCELLED <-----+
```

- conteúdo clínico pode ser ajustado enquanto `DRAFT`;
- após `SUBMITTED`, itens e texto clínico tornam-se imutáveis pela interface comum;
- correção clínica gera nova prescrição vinculada por `replaces`, preservando a anterior;
- transições de estado são feitas somente por services e auditadas;
- `MedicationDispense`/`MedicationDispenseItem`/`StockMovement` concluídos são append-only.

Dispensação pode ser parcial por múltiplos `MedicationDispense`; o saldo dispensável é derivado dos itens já confirmados, sem reescrever dispensações antigas.

## Rotas e Views

Definidas em `contracts/routes.md`.

Padrões:

- CBVs/views Django server-rendered;
- `POST` + CSRF em toda mutação;
- querysets sempre filtrados por RBAC + ABAC;
- objeto clínico fora do escopo retorna 404 quando revelar existência puder expor PHI;
- respostas clínicas e farmacêuticas usam `Cache-Control: private, no-store`;
- conflitos de estoque aparecem como erro operacional seguro.

## Formulários e Validação

Definidos em `contracts/forms.md`.

Validações críticas são repetidas no service dentro da transação. Forms nunca são a única barreira para:

- encontro aberto/acessível;
- transição de status;
- alertas bloqueantes configurados;
- lote ativo/não expirado;
- saldo suficiente;
- idempotência da dispensação.

Formsets podem ser usados para itens de prescrição, mantendo processamento server-side e limites explícitos de quantidade de itens por requisição.

## Segurança Medicamentosa

`apps/clinical/prescription/safety.py` deve ser determinístico e orientado por dados aprovados.

### Interações

- recebe conjunto de `Drug` da prescrição;
- procura pares ativos em `Interaction`;
- não possui lista clínica hardcoded;
- retorna alertas com severidade/referência/bloqueio exatamente como configurados;
- qualquer override futuro exige permissão e contrato clínico específico.

### Alergias

- nunca usa texto livre de auditoria como fonte;
- integra somente com selector PEP estruturado aprovado;
- enquanto a fonte não existir, retorna estado `UNAVAILABLE`, nunca lista vazia interpretável como “sem alergias”;
- UI exige reconhecimento explícito dessa limitação antes da validação.

### Dose

- `DoseRule` é dado de referência com procedência e aprovação;
- idade é calculada de `Patient.birth_date` na data do encontro;
- peso não é solicitado como valor duplicado na prescrição;
- a Spec 004 já fornece `latest_weight_fact()` com `weight_kg` e proveniência técnica, mas o RX não consome esse fato automaticamente enquanto T-NUR-09 não aprovar origem aceitável, atualidade máxima e demais critérios de elegibilidade clínica;
- se a regra exigir um fato ausente ou ainda não elegível, resultado é `NOT_EVALUABLE`, não `PASS`;
- conversões de unidade só serão implementadas quando explicitamente contratadas e testadas.

## Estoque e Concorrência

A dispensação usa:

1. `transaction.atomic()`;
2. locking da prescrição relevante e de todos os `Lot` consumidos (`select_for_update()`);
3. revalidação de autorização/estado/validade/saldo;
4. criação de `MedicationDispense` por `operation_key` única;
5. criação dos itens dispensados;
6. decremento do saldo do lote com constraint de não-negatividade;
7. criação append-only de `StockMovement` para cada lote;
8. evento pós-commit.

Testes PostgreSQL devem disputar o último saldo em conexões independentes e provar que apenas uma operação vencedora consome estoque.

## Fronteira com Estoque/Compras (Spec 009)

Nesta spec, `StockItem`/`Lot` cobrem somente estoque farmacêutico necessário à dispensação. Fornecedor, pedido de compra, recebimento comercial e estoque geral pertencem à Spec 009. A futura integração deve ocorrer por serviço/evento interno e migração contratada, sem criar duas fontes de verdade silenciosas.

## Eventos Internos

Contrato em `contracts/events.asyncapi.yaml`:

- `prescription.created`;
- `prescription.validated`;
- `medication.dispensed`;
- `stock.low`.

Todos são agendados em `transaction.on_commit()`. Payloads contêm UUIDs técnicos, status/quantidades estritamente necessárias e timestamp; não incluem nome do paciente, CPF, instrução clínica, alergia ou justificativa textual.

## PWA

Impacto: sim, porém **network-only** para todas as mutações desta spec.

- telas podem usar o shell PWA enquanto conectadas;
- páginas autenticadas de prescrição/dispensação não entram em cache clínico;
- `AegisOfflineQueue` não é carregado/acionado pelos formulários desta spec;
- perda de conexão impede confirmação;
- administração de medicamento offline pertence à Spec 004 e não autoriza dispensação offline.

## Auditoria

- modelos clínicos/farmacêuticos registrados no `django-auditlog` com exclusão de texto clínico/sensível;
- leituras identificáveis relevantes emitem `ACCESS`;
- auditoria de estoque registra IDs técnicos, quantidade e ator sem copiar PHI;
- logs técnicos não registram conteúdo da prescrição ou alergias.

## Migrações

- migrations apenas do novo app, exceto futura extensão PEP de alergias em PR/spec próprios;
- FKs usam `PROTECT` para registros clínicos/históricos concluídos;
- rollback antes de dados reais pode remover tabelas do app;
- após uso real, rollback de código preserva tabelas e histórico, sem migration destrutiva automática.

## Testes

- modelos/constraints/imutabilidade;
- forms e services;
- transições de estado;
- RBAC + ABAC e negações sem PHI;
- safety engine com dados sintéticos para interação/dose;
- estado explícito de alergia indisponível;
- lote expirado/inativo/saldo insuficiente;
- idempotência de dispensação;
- concorrência PostgreSQL;
- auditlog e eventos sem PHI;
- contrato AsyncAPI;
- teste arquitetural sem nova `/api/`;
- Gherkin + Playwright das jornadas principais;
- axe-core e viewports mobile/tablet;
- PWA network-only.

## Rollout

1. aprovar Spec 003 e contratos;
2. implementar catálogo + referências farmacêuticas sem prescrição ativa;
3. implementar prescrição DRAFT/SUBMITTED e autorização;
4. implementar safety engine genérico com referências sintéticas nos testes;
5. implementar validação farmacêutica e gate de alergia/dose ausente;
6. implementar estoque/lotes/movimentos;
7. implementar dispensação transacional/idempotente;
8. executar concorrência, E2E, a11y, auditoria e PWA;
9. somente habilitar regras clínicas reais após carga de referência/procedência aprovada;
10. automação de alergias e consumo de peso entram apenas após os respectivos gates de governança das fontes clínicas.
