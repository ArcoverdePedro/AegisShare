# Plano Técnico — Spec 002 ADT

## Arquitetura

Criar `apps/clinical/adt` como bounded context separado dentro do monólito Django. O módulo ADT reutiliza `apps.clinical.pep.models.Patient` e, principalmente, o `Encounter` canônico do PEP; não haverá modelo `Encounter` duplicado.

Camadas previstas:

```text
apps/clinical/adt/
  models.py        # Location, Bed, Admission, BedOccupancy, Transfer, Discharge
  forms.py         # formulários server-side
  selectors.py     # consultas autorizadas para mapa/listas/histórico
  services.py      # operações transacionais críticas
  events.py        # emissão pós-commit sem PHI textual
  permissions.py   # RBAC + ABAC e integração com escopo PEP
  views.py         # CBVs Django/HTMX
  urls.py
  consumers.py     # atualização autorizada do mapa
  routing.py
  migrations/
  tests/
```

Templates permanecem em `templates/clinical/adt/`. Nenhuma API REST pública será adicionada.

## Modelo de Dados

Detalhado em `data-model.md`. Resumo:

- `Location`: unidade/setor/quarto lógico, hierárquico opcional;
- `Bed`: leito operacional pertencente a um `Location`;
- `Admission`: início administrativo de uma internação para um `Encounter` PEP;
- `BedOccupancy`: intervalo de ocupação de um leito por uma admissão;
- `Transfer`: movimento append-only entre duas ocupações/localizações;
- `Discharge`: encerramento administrativo da internação.

O estado atual do leito deve ser derivável com segurança de `Bed.operational_status` + ocupação ativa, evitando gravar dois estados concorrentes como fontes de verdade.

## Rotas e Views

Definidas em `contracts/routes.md`. Padrão:

- views HTML completas para navegação;
- partial HTMX separado para o mapa;
- POST para todas as mutações;
- `login_required`/mixins + autorização por capacidade e objeto;
- conflitos de concorrência retornam erro de formulário seguro, não detalhes de banco.

## Formulários e Validação

Definidos em `contracts/forms.md`.

As validações críticas não ficam apenas em `Form.clean()`: disponibilidade de leito, estado do encontro e transições de lifecycle devem ser rechecadas no serviço dentro da transação, com locking/constraint no banco.

Cada POST crítico deve possuir uma `operation_key` opaca gerada no formulário/sessão e consumida idempotentemente pelo serviço para reduzir duplicidade por duplo clique/retry de rede.

## Templates e Componentes HTMX

Definidos em `contracts/htmx.md`.

O mapa de leitos usa HTMX para atualização incremental e Channels apenas como sinal de invalidação/refresh. O WebSocket não transporta nome, CPF, diagnóstico ou conteúdo clínico. A renderização autorizada continua ocorrendo no servidor Django.

## Eventos Internos

Contrato inicial em `contracts/events.asyncapi.yaml`:

- `encounter.admitted`;
- `encounter.transferred`;
- `encounter.discharged`;
- `bed.occupied`;
- `bed.released`;
- `bed.status_changed`.

Eventos são emitidos somente em `transaction.on_commit()`. Payloads usam UUIDs técnicos, estado e timestamp mínimos; consumidores devem buscar dados adicionais por serviços internos autorizados.

## PWA

Impacto: **sim**, mas somente para experiência instalada e conectividade.

Nesta primeira versão:

- GET do mapa continua dependente de rede para dados atuais;
- nenhuma admissão, transferência ou alta entra na fila IndexedDB;
- o service worker continua `network-only` para páginas/mutações ADT;
- perda de conectividade deve mostrar feedback explícito e impedir confirmação da mutação;
- nenhuma exceção será adicionada a T-PWA-07 sem novo contrato aprovado.

Motivo: disponibilidade de leito é altamente concorrente; enfileirar uma transferência offline com estado obsoleto pode criar conflito operacional ou percepção incorreta de ocupação.

## Segurança e LGPD

- RBAC por capacidade ADT (`view_bed_map`, `admit`, `transfer`, `discharge`, `manage_bed_status`);
- ABAC por escopo organizacional/local e, quando houver PHI, por acesso PEP ao paciente;
- usuário sem grant clínico pode receber apenas estado operacional mínimo do leito quando sua função permitir o mapa;
- auditoria de leitura para telas que exibem paciente identificável;
- auditlog exclui PHI textual dos payloads serializados;
- WebSocket revalida autorização antes de cada entrega;
- logs técnicos usam IDs e códigos de erro, nunca nome/CPF/diagnóstico;
- respostas de negação preferem 404 quando revelar existência do objeto seria exposição indevida.

## Concorrência e Consistência

Implementação prevista para operações de leito:

1. iniciar `transaction.atomic()`;
2. selecionar encontro/admissão/leito relevantes com locking apropriado (`select_for_update` quando necessário);
3. revalidar estado e autorização;
4. verificar constraint de ocupação ativa;
5. encerrar/criar intervalos de ocupação;
6. persistir `Transfer`/`Discharge` append-only;
7. atualizar `Encounter` somente quando a transição exigir;
8. registrar auditoria e agendar eventos com `on_commit()`.

A constraint final será validada na implementação contra PostgreSQL e Django 6.x do projeto, mantendo migration reversível.

## Migrações

Previstas migrations apenas para o novo app ADT. Não mover tabelas PEP e não alterar PKs/constraints existentes do `Encounter` nesta primeira fase.

Rollback deve remover somente tabelas ADT se ainda não houver dados reais. Após produção com histórico, rollback de código deve preservar tabelas/dados; migrations destrutivas não serão usadas como rollback operacional.

## Testes

- unitários de modelos e services;
- concorrência PostgreSQL para dupla ocupação;
- views/forms e autorização por papel/objeto;
- auditoria de leitura/escrita;
- Channels para revogação/revalidação;
- contrato de eventos sem PHI textual;
- Gherkin das jornadas de admissão, transferência, conflito e alta;
- Playwright desktop/mobile/tablet;
- axe-core nas telas essenciais;
- regressão PWA garantindo ausência de mutações ADT na fila/cache offline;
- CI completo existente.

## Rollout

1. aprovar Spec 002 e ADR-0008;
2. implementar modelos + constraints + permissões sem UI avançada;
3. entregar mapa de leitos somente leitura;
4. entregar admissão transacional;
5. entregar transferência;
6. entregar alta;
7. habilitar eventos/refresh WebSocket;
8. executar E2E/a11y/concorrência e revisar auditoria;
9. somente depois considerar integrações internas com módulos 003/008.
