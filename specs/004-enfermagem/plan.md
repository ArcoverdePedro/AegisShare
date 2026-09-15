# Plano Técnico — Spec 004 Enfermagem

## Arquitetura

Criar `apps/clinical/nursing` como bounded context dentro do monólito Django **somente após aprovação desta spec**. O app referencia `Encounter` do PEP, consulta contexto ADT quando necessário e referencia `MedicationDispenseItem` da Prescrição/Farmácia para administração. Nenhuma identidade clínica é duplicada.

Estrutura mínima prevista:

```text
apps/clinical/nursing/
  models.py
  forms.py
  permissions.py
  selectors.py
  services.py
  events.py
  views.py
  urls.py
  migrations/
  tests/
templates/clinical/nursing/
```

`selectors.py`, `services.py` e `events.py` só permanecem se o código concreto justificar sua existência; a implementação deve seguir `AGENTS.md`, com FBVs por padrão e sem abstrações especulativas.

Nenhuma API REST pública será criada.

## Modelo de Dados

Detalhado em `data-model.md`. Entidades iniciais:

- `VitalSignsRecord`: snapshot append-only de uma aferição, com uma ou mais medidas estruturadas;
- `MedicationAdministration`: confirmação idempotente de administração ligada a `MedicationDispenseItem`.

Nenhuma tabela própria de paciente, encontro, medicamento, prescrição, estoque ou lote é criada.

## Sinais Vitais

`VitalSignsRecord` guarda campos explícitos em unidades canônicas para evitar uma camada genérica de observações nesta fase. Pelo menos um valor é obrigatório.

Medidas previstas:

- temperatura em °C;
- frequência cardíaca em bpm;
- frequência respiratória em irpm;
- pressão arterial sistólica/diastólica em mmHg;
- SpO2 em %;
- peso em kg.

As validações do servidor garantem apenas integridade estrutural/técnica e limites representacionais seguros. **Não serão codificadas faixas de normalidade, alertas ou interpretação clínica.**

Correções são novos registros usando `replaces`; não existe edição destrutiva do fato anterior.

## Integração futura do peso com RX

O app poderá oferecer selector que retorne:

```text
weight_kg
recorded_at
record_id
recorded_by_id
encounter_id
```

O selector não decide se o peso está clinicamente “atual”. A política de janela temporal, origem aceitável e uso entre encontros depende de governança clínica/farmacêutica. Enquanto ausente, a Spec 003 continua retornando `NOT_EVALUABLE` para regras dependentes de peso.

A futura ativação no safety engine deve ocorrer em PR/tarefa rastreável após fechamento desse gate, sem mudança silenciosa de comportamento.

## Administração de Medicamento

A v1 parte de um `MedicationDispenseItem` já confirmado pela Spec 003. Assim a rastreabilidade de lote é herdada sem criar outra fonte de verdade.

Fluxo inicial:

1. profissional abre medicações do encontro acessível;
2. servidor lista somente itens dispensados compatíveis com o encontro e não administrados pela mesma operação;
3. profissional informa/confirma dose e unidade efetivamente administradas;
4. servidor revalida sessão, capacidade, escopo PEP, encontro, vínculo da dispensação e `operation_key`;
5. `MedicationAdministration` é persistida em transação;
6. auditoria/evento são produzidos após sucesso.

Esta versão não converte unidades nem decide equivalência terapêutica. Estados como recusa, omissão, atraso, substituição, administração parcial ou dose divergente dependem de contrato clínico institucional posterior. Até lá a UI não finge suportá-los.

## Rotas e Views

Contrato em `contracts/routes.md`.

Diretrizes:

- FBVs por padrão;
- `@login_required` e restrição explícita de método;
- `POST` + CSRF para mutações;
- querysets filtrados por RBAC + ABAC;
- objeto fora do escopo deve preferir 404 quando a própria existência puder revelar PHI;
- respostas clínicas usam `Cache-Control: private, no-store`;
- nenhum dado clínico é transportado em query string.

## Autorização

Contrato em `contracts/access-policy.md`.

Capacidades mínimas propostas:

- `nursing.view_nursing`;
- `nursing.record_vitals`;
- `nursing.administer_medication`.

Permissão Django nunca substitui escopo PEP. O contexto ADT/local pode reduzir o universo acessível, mas não cria acesso clínico por si só.

## Offline — piloto de sinais vitais

Contrato em `contracts/offline-vital-signs.md`.

Não criar nova fila. Reutilizar `static/pwa/offline_queue.js` da Spec 014 com `operation_type = nursing.vitals.record`.

Envelope local contém somente IDs técnicos, timestamps e medidas necessárias, dentro do `payload_ciphertext` AES-GCM. O servidor continua sendo a autoridade e reaplica todas as validações.

Política de conflito inicial:

- mesma `idempotency_key`: reconhecer o registro já criado, sem duplicar;
- sessão inválida/permissão perdida: bloquear sincronização;
- encontro encerrado ou não mais acessível: `conflict`, sem inserção automática;
- registro substituído/corrigido por outro fluxo: não sobrescrever; revisão explícita;
- não usar `last-write-wins`.

Administração de medicamento não usa a fila offline.

## Eventos Internos

Contrato em `contracts/events.asyncapi.yaml`:

- `nursing.vitals.recorded`;
- `nursing.medication.administered`.

Eventos são agendados com `transaction.on_commit()` e carregam IDs técnicos + timestamp. Valores de sinais vitais e dose não são copiados para eventos genéricos nesta versão.

## Auditoria

- leitura de histórico identificável relevante gera `ACCESS` conforme padrão PEP;
- criação/correção de sinais vitais é auditável;
- administração é auditável e imutável pela UI;
- conflitos de sincronização são auditáveis com IDs técnicos e motivo codificado, sem payload clínico;
- logs de aplicação não registram medidas, nomes, CPF ou instruções da prescrição.

## Migrações

- migrations somente do novo app `nursing`;
- FKs históricas usam `PROTECT` quando exclusão quebraria rastreabilidade;
- constraints de idempotência no PostgreSQL;
- rollback antes de dados reais pode remover tabelas;
- após uso clínico, rollback de código preserva os dados, sem migration destrutiva automática.

## Testes

- models/constraints;
- forms server-side;
- imutabilidade e `replaces`;
- RBAC + ABAC;
- negação sem PHI;
- idempotência online/offline;
- conflito de sync por encontro encerrado;
- fila local cifrada e ausência de plaintext no IndexedDB;
- logout limpando envelope da sessão conforme Spec 014;
- administração ligada ao dispense/lote correto;
- administração `network-only`;
- auditlog/eventos sem PHI;
- contrato AsyncAPI;
- teste arquitetural de ausência de nova `/api/` pública;
- Gherkin + Playwright;
- axe-core e telefone/tablet.

## Rollout proposto

1. aprovar Spec 004 e contratos;
2. criar app, permissões e migrations mínimas;
3. implementar sinais vitais somente online;
4. validar imutabilidade, autorização e auditoria;
5. integrar o tipo `nursing.vitals.record` à fila offline existente;
6. validar idempotência/conflitos E2E antes de habilitar o piloto;
7. implementar administração de medicamento somente online;
8. validar rastreabilidade até lote e dupla submissão;
9. executar a11y/mobile/PWA/security gates;
10. manter integração automática de peso com RX desligada até aprovação explícita da política clínica de atualidade/origem.

## Gates que permanecem externos

- política institucional de validade temporal/origem do peso para uso automático em RX;
- semântica de recusa, omissão, atraso, dose divergente e demais exceções de administração;
- qualquer faixa normal/anormal, alerta ou score baseado em sinais vitais.

Esses pontos não bloqueiam o registro estruturado básico, mas bloqueiam automatizações clínicas correspondentes.