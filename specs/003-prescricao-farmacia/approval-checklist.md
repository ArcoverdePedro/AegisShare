# Checklist de aprovação — Spec 003 Prescrição e Farmácia

> A Spec 003 foi aprovada pelo mantenedor em 2026-09-14. Este checklist separa arquitetura/runtime implementados do conteúdo clínico de referência que **não** é aprovado implicitamente.

## Arquitetura e ownership

- [x] `Patient` e `Encounter` permanecem canônicos no PEP; a Spec 003 apenas referencia esses modelos.
- [x] Prescrição/farmácia está em `apps/clinical/prescription`, sem nova API REST pública.
- [x] `MedicationRequest`/itens clínicos ficam imutáveis após submissão; correção usa novo registro/substituição rastreável.
- [x] `MedicationSafetyReview`, `MedicationDispense` e `StockMovement` concluídos são append-only.
- [x] Estoque farmacêutico inicial pertence à Spec 003; compras/fornecedores/estoque geral ficam para integração com a Spec 009.

## Segurança clínica

- [x] Interações e regras de dose são data-driven, com fonte, versão, aprovador e data; nenhuma regra terapêutica é hardcoded pelo desenvolvimento.
- [x] `blocking` em `Interaction` é atributo governado e não é inferido automaticamente da severidade.
- [x] A Spec 003 não cria cadastro duplicado de alergias; a extensão PEP foi definida em `specs/001-pep/extensions/allergy-intolerance/`.
- [x] Enquanto `AllergyIntolerance` não estiver implementada/validada, a UI declara checagem automática indisponível e exige revisão manual explícita; nunca exibe “sem alergias conhecidas”.
- [x] Peso não é digitado/copiado ad hoc para alimentar algoritmo; regras dependentes de peso ficam `NOT_EVALUABLE` sem fonte estruturada aprovada.
- [x] Validação farmacêutica da Spec 003 permanece separada da assinatura eletrônica jurídica/ICP-Brasil de T-PEP-08.

## Autorização

- [x] `FUNC` não recebe capacidade farmacêutica automática.
- [x] Mesmo `ADM` exige permissão explícita para ações de prescrever/validar/dispensar.
- [x] RBAC usa permissões Django; ABAC reaplica `can_access_patient()` em todo objeto identificável.
- [x] Objetos clínicos fora do escopo são ocultados/negados sem exposição de PHI.
- [x] Gherkin/Playwright provam negação do papel `CLI` mesmo com permissões RX deliberadamente mal atribuídas.

## Estoque e concorrência

- [x] Dispensação usa `transaction.atomic()`, `select_for_update()` e constraint de saldo não-negativo.
- [x] `operation_key` torna a dispensação idempotente e replay divergente é rejeitado.
- [x] lote expirado/inativo nunca é elegível.
- [x] cada decremento de lote possui `StockMovement` auditável.
- [x] testes PostgreSQL concorrentes disputam o último saldo e provam que apenas uma operação confirma sem saldo negativo/estado parcial.

## Auditoria e eventos

- [x] leituras clínicas identificáveis geram auditoria `ACCESS` nas superfícies publicadas.
- [x] services críticos atribuem mutações ao ator explícito sem depender exclusivamente do middleware.
- [x] `prescription.created`, `prescription.validated`, `medication.dispensed` e `stock.low` são pós-commit.
- [x] payloads AsyncAPI carregam somente IDs/estado/timestamp necessários e não carregam nome, CPF, instrução, alergia ou texto clínico livre.

## PWA, acessibilidade e exposição externa

- [x] prescrição, validação e dispensação permanecem `network-only` nesta versão.
- [x] mutações da Spec 003 permanecem fora de Cache Storage/IndexedDB/Background Sync.
- [x] superfícies clínicas usam `private, no-store, max-age=0` e `Vary` adequado.
- [x] nenhuma nova rota `/api/` foi criada.
- [x] axe-core/WCAG 2.1 A/AA e viewports de telefone/tablet cobrem as superfícies RX essenciais.
- [x] Playwright cobre prescrever → submeter → validar → dispensar e o bloqueio por interação sintética.

## Conteúdo clínico que NÃO é aprovado por este checklist

Continuam exigindo validação clínica/farmacêutica separada antes de uso real em produção:

- base real de interações medicamentosas;
- classificação/severidade/bloqueio real de cada interação;
- regras reais de dose por idade/peso;
- tabelas/conversões clínicas de unidades;
- política institucional para auto-validação prescritor = farmacêutico, se aplicável;
- política institucional para override de alertas bloqueantes;
- terminologia e estados elegíveis de `AllergyIntolerance`;
- fonte estruturada de peso;
- política de fracionamento/devolução/estorno de medicamentos.

Até esses pontos terem fonte e aprovação documentadas, testes e demonstrações usam somente dados sintéticos.

## Gate SDD atual

A superfície técnica implementada da Spec 003 está coberta por serviços transacionais, RBAC+ABAC, auditoria/eventos, Gherkin, testes Django/PostgreSQL e E2E. O fechamento global permanece bloqueado por **T-RX-02** (governança clínica das referências reais) e **T-RX-17** (integrações futuras com Specs 004/009 sem duplicar fonte de verdade).
