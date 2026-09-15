# Tasks — Extensão PEP AllergyIntolerance

> Status: contrato definido em 2026-09-15 para fechar T-RX-03. Implementação automática permanece bloqueada até validação clínica/farmacêutica da terminologia, estados e regras de uso.

- [x] **T-ALLERGY-01** Definir entidade, invariantes, ownership PEP e fronteira de integração RX nesta extensão.
- [ ] **T-ALLERGY-02 — BLOCKED (governança clínica/farmacêutica)** Validar terminologia, estados, criticidade, substância/agente e política institucional para registro/revisão de alergias e intolerâncias. O desenvolvimento não deve escolher esses significados clínicos unilateralmente.
- [ ] **T-ALLERGY-03 — BLOCKED por T-ALLERGY-02** Implementar model/migration somente após aprovação do contrato clínico definitivo.
- [ ] **T-ALLERGY-04 — BLOCKED por T-ALLERGY-02/03** Implementar superfícies PEP, autorização, auditoria e testes após existir fonte estruturada aprovada.
- [ ] **T-ALLERGY-05 — BLOCKED por T-ALLERGY-02/03/04** Integrar a fonte estruturada ao safety engine RX; até lá manter `UNAVAILABLE` + revisão manual explícita e nunca inferir ausência de alergia.
