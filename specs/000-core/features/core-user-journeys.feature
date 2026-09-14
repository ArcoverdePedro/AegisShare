# language: pt
Funcionalidade: Jornadas essenciais do Core
  Como usuário do AegisShare
  Quero autenticar, localizar documentos e compartilhar acesso de forma controlada
  Para que documentos sejam acessíveis apenas pelos fluxos autorizados

  Cenário: Credenciais inválidas não autenticam o usuário
    Dado que estou na página de login
    Quando informo um usuário ou senha inválidos
    Então continuo na página de login
    E vejo a mensagem de credenciais inválidas

  Cenário: Administrador autenticado localiza e abre um documento acessível
    Dado que existe o documento de teste "ci-e2e-document.txt"
    E estou autenticado como administrador
    Quando acesso a listagem de arquivos
    Então vejo o documento de teste e seu proprietário
    Quando abro o documento
    Então vejo seus detalhes de segurança e integridade

  Cenário: Administrador concede acesso direto a outro usuário
    Dado que estou autenticado como administrador
    E abri o documento de teste
    Quando concedo acesso ao usuário "ci-e2e-recipient"
    Então o usuário aparece entre os acessos diretos do documento
    E esse usuário consegue autenticar e abrir o documento pela listagem de arquivos

  Cenário: Link público protegido exige senha e respeita permissões
    Dado que estou autenticado como administrador
    E abri o documento de teste
    Quando crio um link temporário protegido por senha
    E desabilito visualização e download nesse link
    Então o token completo é exibido apenas após a criação
    Quando acesso o link sem estar autenticado
    Então preciso informar a senha do link
    Quando informo a senha correta
    Então vejo os metadados do documento
    E não vejo ações de visualização ou download
