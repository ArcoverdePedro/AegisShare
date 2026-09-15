# language: pt
Funcionalidade: Ciclo clínico de prescrição e dispensação
  Como equipe assistencial e farmacêutica autorizada
  Quero prescrever, revisar e dispensar medicação com safety gates e rastreabilidade
  Para manter o ciclo do medicamento explícito, auditável e transacional

  Cenário: prescrever, submeter, validar e dispensar por lote preserva o fluxo clínico
    Dado um encontro aberto de paciente no escopo PEP do profissional
    E um medicamento ativo com lote válido e saldo disponível
    Quando o prescritor registra uma prescrição estruturada e a submete
    E o farmacêutico confirma a revisão manual de alergias porque a fonte estruturada está indisponível
    E não existe achado de referência sintética bloqueante
    Então a prescrição pode ser validada
    E a dispensação online baixa o lote dentro de uma única transação
    E a dispensação preserva o vínculo entre prescrição, item, lote e movimentação de estoque

  Cenário: interação sintética bloqueante impede validação sem perder a revisão
    Dado uma prescrição submetida contendo dois medicamentos
    E uma Interaction sintética ativa, aprovada e marcada como bloqueante para esse par
    Quando o farmacêutico confirma a revisão manual de alergias e tenta validar
    Então a prescrição permanece SUBMITTED
    E o MedicationSafetyReview é preservado como registro append-only
    E o achado bloqueante referencia a Interaction sintética utilizada
