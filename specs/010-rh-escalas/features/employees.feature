# language: pt
Funcionalidade: Manter cadastro funcional sem alterar acesso ou vínculo jurídico
  # Critérios cobertos pelos testes Django e Playwright referenciados em validation.md.

  Cenário: CA-HR-01 Cadastro mínimo e vínculo único
    Dado staff interno com capacidades de consulta e criação
    Quando salva setor e função válidos para usuário ativo ADM ou FUNC sem perfil
    Então há um Employee único com identidade do usuário existente
    E strings obrigatórias têm trim externo e limites validados
    Mas usuário cliente, inativo ou já vinculado não recebe novo perfil
    E concorrência PostgreSQL não cria dois perfis para o mesmo usuário

  Cenário: CA-HR-02 Gestão e associação preservada
    Dado perfil mantido pelo Admin com permissões nativas explícitas
    Quando edita setor, função ou active
    Então associação original é preservada inclusive contra POST adulterado
    E exclusão individual e em lote são bloqueadas
    E revogação de capacidade bloqueia salvar formulário já aberto

  Cenário: CA-HR-03 Status e identidade sem efeito de autenticação
    Quando desativa Employee ou usuário associado depois fica inativo ou CLI
    Então o perfil e a associação são preservados e consultáveis por operador RH autorizado
    E Employee não altera login, papel, staff, superusuário, grupos, capacidades ou grants PEP
    E nome exibido acompanha User atual sem promessa de snapshot ou habilitação clínica

  Cenário: CA-HR-04 Consulta por capacidade explícita
    Dado consulta institucional de perfis ativos e inativos aprovada
    Então profissional interno com hr.view_employee consulta todos os perfis
    Mas perfil próprio, papel ADM ou permissão de outro módulo não substituem a capacidade
    E cliente com capacidade e usuário sem sessão não recebem acesso equivalente
    E revogação remove acesso ao detalhe e à lista

  Cenário: CA-HR-05 Paginação e apresentação mínima
    Dado mais de 25 perfis e usuários sem Employee
    Quando consulta lista e detalhe
    Então a lista renderiza 25 perfis e audita somente a página
    E detalhe mostra nome atual, username, setor, função e estado cadastral
    E não mostra contatos ou campos RBAC nem consulta usuário por registro
    E usuários sem perfil não são apresentados como funcionários cadastrados

  Cenário: CA-HR-06 Auditoria e falhas
    Quando auditoria CREATE ou UPDATE ou LogEntry Admin falha
    Então a mutação é revertida sem confirmação parcial
    E falha ACCESS nas FBVs impede conteúdo pessoal e reverte o lote
    E logs não copiam nomes, setores ou funções
    E User referenciado não pode ser removido
    E a fronteira entre alterações Admin e ACCESS das FBVs é documentada sem declarar leitura Admin integralmente auditada

  Cenário: CA-HR-07 HTTP, dispositivos e offline
    Quando usa mutação sem CSRF ou FBV com método inadequado
    Então a operação é impedida preservando headers privados
    E erros de banco ou auditoria são genéricos sem traceback ou dados pessoais
    E telefone/tablet não têm overflow ou violações axe sérias/críticas nas páginas e forms contratados
    E offline não confirma nem armazena cadastro, formulário ou página privada
