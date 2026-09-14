# Tasks — Spec 002 ADT

> Status: documentação e contratos preparados; aguardando aprovação explícita da Spec 002 e ADR-0008 antes de qualquer implementação de runtime.

- [x] **T-ADT-01** Fechar `data-model.md`, constraints PostgreSQL e ownership do `Encounter`. RF-ADT-01/02/04/05/06. O modelo mantém `Encounter` canônico no PEP conforme ADR-0008, define ocupação ativa com `UniqueConstraint(..., condition=Q(ended_at__isnull=True))` por leito e por admissão e preserva histórico append-only.
- [x] **T-ADT-02** Fechar matriz RBAC + ABAC e capacidades ADT, incluindo exposição mínima do mapa sem grant clínico. RF-ADT-03/07/08. A política está em `contracts/access-policy.md`, usando permissões/grupos Django para capacidades finas e escopo PEP/local como ABAC deny-by-default.
- [ ] **T-ADT-03** Criar `apps/clinical/adt` e migrations iniciais reversíveis. RF-ADT-01/03/04/05.
- [ ] **T-ADT-04** Implementar `Location`, `Bed` e `BedOccupancy` com prevenção de dupla ocupação ativa. RF-ADT-02/03/11.
- [ ] **T-ADT-05** Implementar admissão transacional e idempotente usando `Encounter` PEP aberto/internação. RF-ADT-01/02/11.
- [ ] **T-ADT-06** Implementar mapa de leitos server-rendered + partial HTMX sem exposição indevida de PHI. RF-ADT-03/07.
- [ ] **T-ADT-07** Implementar transferência append-only, encerrando origem e ocupando destino atomicamente. RF-ADT-04/06/11.
- [ ] **T-ADT-08** Implementar alta transacional, liberação do leito e fechamento consistente do `Encounter`. RF-ADT-05/06.
- [ ] **T-ADT-09** Integrar auditoria explícita de leitura/escrita e eventos pós-commit sem PHI textual. RF-ADT-08/10.
- [ ] **T-ADT-10** Implementar atualização do mapa via Channels como sinal de invalidação, com revalidação de autorização. RF-ADT-09.
- [ ] **T-ADT-11** Criar testes de concorrência PostgreSQL para admissão/transferência simultânea. RF-ADT-02/11.
- [ ] **T-ADT-12** Criar Gherkin + Playwright das jornadas principais e negações de acesso. RF-ADT-01/03/04/05/07.
- [ ] **T-ADT-13** Executar axe-core e validação mobile/tablet do mapa e formulários críticos. RNF-ADT-06.
- [ ] **T-ADT-14** Garantir via testes que mutações ADT permanecem fora de cache/fila offline PWA. RF-ADT-12.
- [ ] **T-ADT-15** Atualizar AsyncAPI, documentação e rastreabilidade final; confirmar ausência de nova API REST pública. RF-ADT-10 / RNF-ADT-03.
