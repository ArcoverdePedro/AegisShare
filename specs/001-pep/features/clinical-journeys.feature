# language: pt
Funcionalidade: Jornadas clínicas principais do PEP
  Como profissional interno autorizado
  Quero cadastrar e consultar pacientes, encontros e evoluções
  Para manter um prontuário longitudinal rastreável sem ampliar o escopo de acesso

  Cenário: Profissional cadastra paciente e inicia encontro
    Dado que estou autenticado como profissional interno
    Quando cadastro um paciente com identificador válido
    Então recebo acesso ao prontuário criado
    Quando inicio um novo encontro clínico
    Então o encontro fica aberto e vinculado ao profissional autenticado

  Cenário: Profissional registra evolução e adendo sem alterar o original
    Dado que existe um paciente acessível com encontro aberto
    Quando registro uma evolução clínica
    Então vejo o registro como imutável
    Quando registro um adendo com motivo e conteúdo
    Então um novo registro é criado como adendo
    E a evolução original permanece disponível e inalterada

  Cenário: Usuário sem vínculo não acessa prontuário
    Dado que existe um prontuário criado por outro profissional
    E estou autenticado como profissional sem vínculo com esse paciente
    Quando tento abrir diretamente o prontuário
    Então recebo uma resposta de recurso não encontrado
    E o nome do paciente não é revelado no corpo da resposta

  Cenário: Telas clínicas essenciais atendem verificação automatizada de acessibilidade
    Dado que estou autenticado e autorizado no PEP
    Quando abro a lista, o prontuário e os formulários clínicos principais
    Então não existem violações críticas ou sérias detectadas pelo axe-core
    E as ações principais continuam utilizáveis em viewport de tablet e telefone
