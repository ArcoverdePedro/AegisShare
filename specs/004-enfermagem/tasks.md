# Tasks — Spec 004 Enfermagem

> Status: proposta. A criação desta documentação não libera implementação clínica; o mantenedor deve aprovar a Spec 004 antes de T-NUR-03 em diante.

- [x] **T-NUR-01** Definir `spec.md`, `plan.md` e `data-model.md` do recorte inicial de Enfermagem. RF-NUR-01/02/09.
- [x] **T-NUR-02** Definir contratos iniciais de acesso, rotas, offline, administração, eventos e critérios de aceitação. RF-NUR-06/07/09/12/13/14.
- [ ] **T-NUR-03 — BLOCKED até aprovação da Spec 004** Criar `apps/clinical/nursing`, permissões e migrations reversíveis. RF-NUR-01/13; RNF-NUR-07.
- [ ] **T-NUR-04 — BLOCKED até T-NUR-03** Implementar `VitalSignsRecord`, forms e FBVs online, com pelo menos uma medida e unidades canônicas. RF-NUR-02/03/04.
- [ ] **T-NUR-05 — BLOCKED até T-NUR-04** Implementar correção append-only via `replaces` e impedir edição/exclusão destrutiva pela UI. RF-NUR-05.
- [ ] **T-NUR-06 — BLOCKED até T-NUR-04/05** Implementar idempotência server-side para sinais vitais por `idempotency_key`. RF-NUR-06/07.
- [ ] **T-NUR-07 — BLOCKED até T-NUR-06** Habilitar o piloto PWA `nursing.vitals.record` usando exclusivamente a fila cifrada da Spec 014, com revalidação de sessão/autorização e conflito explícito. RF-NUR-06/07; RNF-NUR-08.
- [ ] **T-NUR-08 — BLOCKED até T-NUR-04** Implementar selector de peso que exponha valor + proveniência sem decidir elegibilidade clínica. RF-NUR-08.
- [ ] **T-NUR-09 — BLOCKED (governança clínica/farmacêutica)** Aprovar política de origem aceitável e atualidade máxima do peso para consumo automático pelo RX. RF-NUR-08. Até lá a integração RX permanece desligada/`NOT_EVALUABLE`.
- [ ] **T-NUR-10 — BLOCKED até T-NUR-03 e aprovação da Spec 004** Implementar administração online ligada a `MedicationDispenseItem`, idempotente por `operation_key`, sem conversão automática de unidade. RF-NUR-09/10/11/12.
- [ ] **T-NUR-11 — BLOCKED (governança clínica/operacional)** Definir semântica institucional para recusa, omissão, atraso, dose divergente, administração parcial e demais exceções antes de adicioná-las ao modelo/UI. Esta tarefa não bloqueia o registro v1 de administração efetivamente confirmada.
- [ ] **T-NUR-12 — BLOCKED até T-NUR-04/07/10** Integrar auditoria explícita de leitura/mutação e eventos internos sem PHI. RF-NUR-14.
- [ ] **T-NUR-13 — BLOCKED até implementação** Criar testes unitários/views/security, incluindo RBAC + ABAC, imutabilidade, idempotência e negações sem PHI.
- [ ] **T-NUR-14 — BLOCKED até implementação** Criar/automatizar cenários Gherkin + Playwright de sinais vitais online/offline, conflito de sincronização e administração network-only.
- [ ] **T-NUR-15 — BLOCKED até implementação** Executar axe-core e validação mobile/tablet nas superfícies essenciais. RNF-NUR-05.
- [ ] **T-NUR-16 — BLOCKED até implementação** Validar ausência de plaintext clínico em cache/IndexedDB/logs e limpeza no logout conforme Spec 014. RNF-NUR-04/06/08.
- [ ] **T-NUR-17 — BLOCKED até implementação** Atualizar rastreabilidade final, AsyncAPI e documentação, confirmando ausência de nova API REST pública. RNF-NUR-03.
