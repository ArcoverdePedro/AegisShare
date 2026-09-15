# language: pt
Funcionalidade: Enfermagem — sinais vitais e administração de medicamento
  Como profissional assistencial autorizado
  Quero registrar fatos de enfermagem com rastreabilidade
  Para manter o prontuário consistente sem perder segurança, histórico ou proveniência

  Cenário: registrar sinais vitais em encontro aberto
    Dado um profissional com capacidade de registrar sinais vitais
    E acesso PEP ao paciente
    E um encontro aberto
    Quando ele registra pelo menos uma medida válida
    Então o registro fica vinculado ao encontro canônico
    E autor, momento da aferição e momento de persistência ficam rastreáveis
    E o histórico anterior não é alterado

  Cenário: corrigir sinais vitais preservando o original
    Dado um registro de sinais vitais já persistido
    Quando um profissional autorizado corrige a aferição
    Então um novo registro referencia o anterior por replaces
    E o registro original permanece inalterado

  Cenário: enfileirar sinais vitais durante perda de conexão
    Dado o PWA instalado
    E uma sessão autenticada
    E um encontro aberto acessível
    Quando a conexão cai antes de confirmar sinais vitais
    Então a operação nursing.vitals.record é armazenada somente como payload cifrado
    E a interface informa que o registro ainda está pendente de sincronização

  Cenário: retry offline não duplica sinais vitais
    Dado um envelope nursing.vitals.record já confirmado no servidor
    Quando o dispositivo reenviar a mesma idempotency_key
    Então o servidor reconhece o registro existente
    E não cria um segundo VitalSignsRecord

  Cenário: encontro encerrado antes do sync gera conflito
    Dado sinais vitais pendentes criados quando o encontro estava aberto
    E o encontro foi encerrado antes da sincronização
    Quando o dispositivo tenta sincronizar
    Então nenhum registro é inserido silenciosamente
    E a operação fica em conflito para revisão explícita

  Cenário: perda de acesso antes do sync impede persistência
    Dado sinais vitais pendentes no dispositivo
    E o profissional perdeu o escopo PEP antes da sincronização
    Quando o dispositivo tenta sincronizar
    Então o servidor recusa a operação
    E não revela dados clínicos adicionais na resposta de erro

  Cenário: peso estruturado não libera regra RX sem governança
    Dado um VitalSignsRecord com weight_kg
    E a política institucional de atualidade e origem do peso ainda não aprovada
    Quando o safety engine RX avalia regra dependente de peso
    Então o peso não é consumido automaticamente como elegível
    E o resultado continua NOT_EVALUABLE

  Cenário: administrar medicamento online preserva lote e prescrição
    Dado um item prescrito validado e dispensado por lote
    E um profissional autorizado com escopo PEP
    Quando ele confirma online a administração com operation_key inédita
    Então uma única MedicationAdministration é criada
    E a rastreabilidade alcança o dispense item, lote, item prescrito e encontro

  Cenário: retry de administração não duplica o ato
    Dado uma administração já confirmada
    Quando o mesmo operation_key é reenviado
    Então o servidor reconhece a operação existente
    E não cria segunda MedicationAdministration

  Cenário: administração não funciona offline
    Dado o PWA instalado
    Quando a conexão cai antes de confirmar a administração
    Então a confirmação não é persistida
    E nenhuma operação de administração entra no Cache Storage ou IndexedDB offline

  Cenário: usuário fora do escopo não vê dados de enfermagem
    Dado um encontro pertencente a paciente fora do escopo PEP do usuário
    Quando ele tenta abrir uma rota de enfermagem
    Então o sistema nega o acesso sem revelar paciente, sinais vitais ou medicamentos
