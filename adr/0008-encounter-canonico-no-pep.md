# ADR-0008 — `Encounter` canônico permanece no PEP

- Status: Aceito
- Data: 2026-09-14
- Relacionado: Specs 001 (PEP) e 002 (ADT)

## Contexto

O SDD lista `Encounter` entre os modelos conceituais do PEP e também no escopo ADT. No repositório atual, `apps.clinical.pep.models.Encounter` já está implementado, migrado e usado por evoluções clínicas, auditoria, autorização e eventos.

Criar um segundo `Encounter` dentro de `apps.clinical.adt` produziria duas fontes de verdade para o mesmo atendimento, exigindo sincronização bidirecional e aumentando o risco de alta/admissão divergirem do prontuário.

## Decisão

O `Encounter` continuará pertencendo ao bounded context PEP como entidade canônica do atendimento clínico.

O ADT:

- referencia `pep.Encounter` por `ForeignKey`/`OneToOneField`;
- adiciona `Admission`, `BedOccupancy`, `Transfer` e `Discharge` para o lifecycle operacional;
- pode alterar somente os campos do `Encounter` necessários à transição ADT por meio de serviço transacional explícito;
- não cria tabela/modelo `adt.Encounter`;
- não replica nome, CPF ou conteúdo clínico em entidades de movimento quando o ID técnico for suficiente.

## Consequências positivas

- uma única identidade para o atendimento;
- evoluções e ADT apontam para o mesmo UUID;
- alta pode fechar o encontro na mesma transação;
- menos risco de divergência e migrações duplicadas;
- eventos internos podem usar `encounter_id` comum entre módulos.

## Consequências e cuidados

- ADT passa a depender formalmente da Spec 001;
- alterações de lifecycle do encontro precisam de contrato entre os módulos;
- serviços ADT não devem importar views/forms do PEP, apenas modelos/selectors/services públicos internos aprovados;
- mudanças futuras na semântica de `Encounter.status` exigem revisão conjunta das Specs 001 e 002.

## Alternativas rejeitadas

### Duplicar `Encounter` em ADT

Rejeitado por criar sincronização, ambiguidade de ownership e risco de inconsistência clínica.

### Mover imediatamente `Encounter` do PEP para ADT

Rejeitado neste estágio porque quebraria migrations, imports, content types, auditlog e testes já estabilizados do PEP. Uma eventual realocação física pode ser avaliada futuramente, mas não é necessária para manter separação lógica de bounded contexts.
