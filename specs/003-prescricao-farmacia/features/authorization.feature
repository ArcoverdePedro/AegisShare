# language: pt
Funcionalidade: Autorização deny-by-default nas superfícies RX publicadas
  Como mantenedor do módulo de Prescrição e Farmácia
  Quero provar que papéis externos continuam bloqueados
  Para que uma permissão Django atribuída por engano não exponha dados farmacêuticos

  Esquema do Cenário: papel CLI permanece negado nas superfícies RX mesmo com permissões mal atribuídas
    Dado um usuário autenticado com papel CLI
    E permissões RX de catálogo e estoque deliberadamente atribuídas por engano
    Quando ele tenta acessar "<rota>"
    Então a resposta HTTP é 403
    E nenhum medicamento da superfície protegida é renderizado

    Exemplos:
      | rota                                                           |
      | /medicamentos/                                                 |
      | /medicamentos/novo/                                            |
      | /medicamentos/00000000-0000-0000-0000-000000000001/editar/    |
      | /estoque-farmacia/                                             |
