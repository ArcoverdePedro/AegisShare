# Checklist de aprovação — Spec 003 Prescrição e Farmácia

> A Spec 003 foi aprovada pelo mantenedor em 2026-09-14. Este checklist separa as decisões arquiteturais aprovadas do conteúdo clínico de referência que **não** é aprovado implicitamente.

## Arquitetura e ownership

- [x] `Patient` e `Encounter` permanecem canônicos no PEP; a Spec 003 apenas referencia esses modelos.
- [x] Prescrição/farmácia será `apps/clinical/prescription`, sem API REST pública.
- [x] `MedicationRequest`/itens clínicos ficam imutáveis após submissão; correção gera novo registro/substituição rastreável.
- [x] `MedicationDispense` e `StockMovement` concluídos são append-only.
- [x] Estoque farmacêutico inicial pertence à Spec 003; compras/fornecedores/estoque geral ficam na Spec 009.

## Segurança clínica

- [x] Interações e regras de dose serão **data-driven**, com fonte, versão, aprovador e data; nenhuma regra terapêutica será hardcoded pelo desenvolvimento.
- [x] `blocking` em `Interaction` é atributo de referência aprovado e não é inferido automaticamente da severidade pelo código.
- [x] A Spec 003 não criará cadastro duplicado de alergias; a fonte estruturada futura deve pertencer ao PEP.
- [x] Enquanto não houver fonte estruturada de alergias, a UI exibirá checagem automática indisponível e nunca “sem alergias conhecidas”.
- [x] Peso não será digitado/copiado ad hoc na prescrição para alimentar algoritmo; regras dependentes de peso ficam `NOT_EVALUABLE` até existir fonte clínica estruturada aprovada.
- [x] Validação farmacêutica da Spec 003 não será chamada de assinatura eletrônica jurídica/ICP-Brasil; T-PEP-08 continua separado.

## Autorização

- [x] `FUNC` não recebe capacidade farmacêutica automática.
- [x] Mesmo `ADM` exige permissão explícita para ações clínicas de prescrever/validar/dispensar; o escopo PEP global do administrador não é, sozinho, licença profissional.
- [x] RBAC usa permissões Django; ABAC reaplica `can_access_patient()` em todo objeto identificável.
- [x] Fora do escopo, detalhes clínicos retornam 404 quando necessário para não revelar existência/PHI.

## Estoque e concorrência

- [x] Dispensação usará `transaction.atomic()`, locks e constraint de saldo não-negativo.
- [x] `operation_key` torna a dispensação idempotente.
- [x] lote expirado/inativo nunca é elegível.
- [x] cada decremento de lote possui `StockMovement` auditável.
- [ ] testes PostgreSQL concorrentes disputam o último saldo antes do merge da etapa de dispensação.

## PWA e exposição externa

- [x] prescrição, validação e dispensação permanecem `network-only` nesta versão;
- [x] nenhuma mutação da Spec 003 entra em Cache Storage/IndexedDB/Background Sync;
- [x] nenhuma nova rota `/api/` é criada;
- [x] eventos internos têm payload técnico mínimo e sem PHI textual.

## Conteúdo clínico que NÃO é aprovado por este checklist

Mesmo após aprovação da Spec 003, continuam exigindo validação clínica/farmacêutica separada antes de produção:

- base real de interações medicamentosas;
- classificação/severidade/bloqueio real de cada interação;
- regras reais de dose por idade/peso;
- tabelas de conversão clínica de unidades;
- política institucional para auto-validação prescritor = farmacêutico, se aplicável;
- política institucional para override de alertas bloqueantes;
- fonte/modelo estruturado de alergias;
- fonte/modelo estruturado de peso;
- política de fracionamento/devolução/estorno de medicamentos.

Testes de desenvolvimento usarão dados sintéticos até esses itens terem fonte e aprovação documentadas.

## Gate SDD

A aprovação do mantenedor em 2026-09-14 liberou a implementação incremental. O runtime continua sujeito aos gates clínicos acima e cada entrega deve passar migrations versionadas, testes, segurança e CI antes do merge automático.
