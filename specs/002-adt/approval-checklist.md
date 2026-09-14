# Checklist de aprovação — Spec 002 ADT

Este documento consolida as decisões que precisam de aceite explícito do mantenedor antes da primeira alteração de runtime do módulo ADT.

## Decisões arquiteturais

- [ ] **`Encounter` canônico permanece no PEP.** O ADT referencia `apps.clinical.pep.models.Encounter` e não cria um segundo modelo concorrente. Ver ADR-0008.
- [ ] **Novo bounded context `apps/clinical/adt`.** `Location`, `Bed`, `Admission`, `BedOccupancy`, `Transfer` e `Discharge` pertencem ao ADT.
- [ ] **PostgreSQL é a fonte de verdade de ocupação.** Um leito e uma admissão podem ter no máximo uma `BedOccupancy` ativa, protegida por constraint parcial e revalidação transacional.
- [ ] **Alta fecha o encontro na mesma transação.** `Discharge`, liberação do leito e `Encounter.status/ended_at` devem permanecer consistentes atomicamente.
- [ ] **Transferência é append-only.** A ocupação de origem é encerrada e a de destino criada sem editar/destruir o histórico concluído.

## Autorização e privacidade

- [ ] **RBAC fino usa permissões/grupos Django.** Ser `FUNC` não concede automaticamente capacidades ADT.
- [ ] **ABAC PEP continua obrigatório para PHI.** Permissão ADT operacional não concede acesso ao prontuário ou identificação do ocupante.
- [ ] **Mapa pode expor estado operacional mínimo sem PHI.** Usuário com `adt.view_bed_map`, mas sem escopo clínico do ocupante, recebe somente estado/disponibilidade permitidos.
- [ ] **`CLI` permanece deny-by-default.** Nenhuma superfície ADT é liberada ao papel cliente nesta fase.
- [ ] **HTMX/WebSocket revalidam acesso no servidor.** Eventos em tempo real carregam somente IDs técnicos/estado necessário para invalidação e nunca nome, CPF, diagnóstico ou texto clínico.

## PWA e integrações

- [ ] **Mutações ADT são `network-only`.** Admissão, transferência e alta não entram no IndexedDB/background sync nesta versão.
- [ ] **Sem API REST pública.** Rotas ADT são Django views/forms/HTMX/WebSocket autenticados por sessão.
- [ ] **Eventos internos são pós-commit.** `encounter.admitted`, `encounter.transferred`, `encounter.discharged`, `bed.occupied`, `bed.released` e `bed.status_changed` são emitidos apenas após confirmação da transação e sem PHI textual.

## Qualidade obrigatória antes de concluir a Spec 002

- [ ] testes unitários e de views;
- [ ] testes PostgreSQL de concorrência/dupla ocupação;
- [ ] testes de autorização e auditoria;
- [ ] Gherkin + Playwright das jornadas principais;
- [ ] axe-core e validação mobile/tablet;
- [ ] regressão PWA provando ausência de cache/fila offline para mutações ADT;
- [ ] lint, Django system check, migrations reversíveis e CI completo.

## Gate

A presença deste checklist no repositório **não equivale a aprovação**. A implementação começa somente após manifestação explícita do mantenedor aprovando a Spec 002 e o ADR-0008. Após o aceite, o status da spec/ADR deve ser atualizado em commit separado antes de `T-ADT-03`.
