# Checklist de aprovação — Spec 003 Prescrição e Farmácia

> Este checklist separa decisões arquiteturais que podem ser aprovadas agora de conteúdo clínico de referência que **não** é aprovado implicitamente com esta spec.

## Arquitetura e ownership

- [ ] `Patient` e `Encounter` permanecem canônicos no PEP; a Spec 003 apenas referencia esses modelos.
- [ ] Prescrição/farmácia será `apps/clinical/prescription`, sem API REST pública.
- [ ] `MedicationRequest`/itens clínicos ficam imutáveis após submissão; correção gera novo registro/substituição rastreável.
- [ ] `MedicationDispense` e `StockMovement` concluídos são append-only.
- [ ] Estoque farmacêutico inicial pertence à Spec 003; compras/fornecedores/estoque geral ficam na Spec 009.

## Segurança clínica

- [ ] Interações e regras de dose serão **data-driven**, com fonte, versão, aprovador e data; nenhuma regra terapêutica será hardcoded pelo desenvolvimento.
- [ ] `blocking` em `Interaction` é atributo de referência aprovado e não é inferido automaticamente da severidade pelo código.
- [ ] A Spec 003 não criará cadastro duplicado de alergias; a fonte estruturada futura deve pertencer ao PEP.
- [ ] Enquanto não houver fonte estruturada de alergias, a UI exibirá checagem automática indisponível e nunca “sem alergias conhecidas”.
- [ ] Peso não será digitado/copied ad hoc na prescrição para alimentar algoritmo; regras dependentes de peso ficam `NOT_EVALUABLE` até existir fonte clínica estruturada aprovada.
- [ ] Validação farmacêutica da Spec 003 não será chamada de assinatura eletrônica jurídica/ICP-Brasil; T-PEP-08 continua separado.

## Autorização

- [ ] `FUNC` não recebe capacidade farmacêutica automática.
- [ ] Mesmo `ADM` exige permissão explícita para ações clínicas de prescrever/validar/dispensar; o escopo PEP global do administrador não é, sozinho, licença profissional.
- [ ] RBAC usa permissões Django; ABAC reaplica `can_access_patient()` em todo objeto identificável.
- [ ] Fora do escopo, detalhes clínicos retornam 404 quando necessário para não revelar existência/PHI.

## Estoque e concorrência

- [ ] Dispensação usa `transaction.atomic()`, locks e constraint de saldo não-negativo.
- [ ] `operation_key` torna a dispensação idempotente.
- [ ] lote expirado/inativo nunca é elegível.
- [ ] cada decremento de lote possui `StockMovement` auditável.
- [ ] testes PostgreSQL concorrentes disputam o último saldo antes do merge de implementação.

## PWA e exposição externa

- [ ] prescrição, validação e dispensação permanecem `network-only` nesta versão;
- [ ] nenhuma mutação da Spec 003 entra em Cache Storage/IndexedDB/Background Sync;
- [ ] nenhuma nova rota `/api/` é criada;
- [ ] eventos internos têm payload técnico mínimo e sem PHI textual.

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

Nenhum model/view/service/migration do módulo 003 deve ser criado antes da aprovação deste PR de especificação. Após aprovação, a implementação começa por catálogo/modelos/permissões e permanece sujeita aos gates clínicos acima.
