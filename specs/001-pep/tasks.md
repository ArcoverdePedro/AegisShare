# Tasks — Spec 001 PEP

> Spec aprovada em 2026-09-11. Implementação liberada conforme contratos e rastreabilidade.

- [x] **T-PEP-01** Criar `data-model.md` com entidades, chaves, constraints e retenção. RF-PEP-01/03/04.
- [x] **T-PEP-02** Validar regras de identificação e deduplicação de paciente. RF-PEP-01.
- [x] **T-PEP-03** Fechar matriz RBAC + ABAC do PEP. RF-PEP-07/08.
- [x] **T-PEP-04** Implementar app `apps/clinical/pep` e migrations iniciais reversíveis. RF-PEP-01/04.
- [x] **T-PEP-05** Implementar lista/pesquisa/cadastro/detalhe de paciente. RF-PEP-01/02/03.
- [x] **T-PEP-06** Implementar encontros clínicos. RF-PEP-04.
- [x] **T-PEP-07** Implementar evolução clínica e histórico imutável com adendos append-only. RF-PEP-05.
- [ ] **T-PEP-08** Definir e implementar assinatura após validação jurídica/operacional. RF-PEP-06.
- [x] **T-PEP-09** Integrar auditoria de leitura/escrita e notificações internas WebSocket sem PHI no payload. RF-PEP-07/09.
- [ ] **T-PEP-10** Consolidar testes de autorização, auditoria e jornadas clínicas restantes.
- [ ] **T-PEP-11** Criar cenários Gherkin e E2E das jornadas principais.
- [ ] **T-PEP-12** Executar axe-core e validação mobile/tablet.
