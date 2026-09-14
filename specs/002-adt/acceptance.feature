# language: pt
Funcionalidade: Jornada ADT segura e consistente
  Como equipe hospitalar autorizada
  Quero admitir, transferir e dar alta por interfaces internas
  Para manter ocupação e histórico consistentes sem expor PHI indevidamente

  Cenário: admitir, transferir e dar alta em uma internação
    Dado um profissional com capacidades ADT, escopo PEP e acesso ao local
    E um encontro de internação aberto
    E dois leitos disponíveis no seu escopo operacional
    Quando ele admitir o paciente no primeiro leito
    Então o primeiro leito deve aparecer como ocupado
    E a identificação do paciente deve aparecer somente porque o profissional possui escopo PEP
    Quando ele transferir a internação para o segundo leito
    Então o primeiro leito deve voltar a disponível
    E o segundo leito deve aparecer como ocupado
    Quando ele registrar a alta para domicílio
    Então o segundo leito deve voltar a disponível
    E o paciente não deve permanecer como ocupante no mapa

  Cenário: negar mapa a usuário sem capacidade ADT
    Dado um usuário interno autenticado sem a capacidade de visualizar mapa de leitos
    Quando ele tentar acessar o mapa
    Então o servidor deve negar a requisição
    E a resposta não deve revelar dados identificáveis de pacientes

  Cenário: ocultar PHI de ocupante sem escopo clínico
    Dado um usuário com capacidade de visualizar mapa e acesso ao local
    E um leito ocupado por paciente fora do seu escopo PEP
    Quando ele consultar o mapa
    Então ele deve visualizar que o leito está ocupado
    Mas não deve receber nome, identificador ou outro dado identificável do paciente

  Cenário: manter interfaces essenciais acessíveis em telefone e tablet
    Dado um profissional autorizado autenticado
    Quando ele abrir o mapa e os formulários críticos em viewport de telefone ou tablet
    Então não deve haver overflow horizontal da página
    E não deve haver violações WCAG 2.1 A ou AA com impacto sério ou crítico detectadas pelo axe-core
