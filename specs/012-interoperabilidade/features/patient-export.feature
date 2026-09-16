# language: pt
Funcionalidade: Exportação interna de cadastro mínimo por arquivo
  # Cobertura Django/Playwright vinculada em ../spec.md; CA-INT-05 usa injeção de falha nos testes Django.

  Cenário: CA-INT-01 Exportar paciente acessível
    Dado um profissional interno com capacidade de exportação e acesso a um paciente ativo
    Quando confirma a exportação pelo formulário com CSRF válido
    Então recebe um arquivo Patient R4 JSON
    E um recibo auditado identifica o ator, o paciente e o hash dos bytes entregues
    E nenhum cadastro clínico é alterado

  Cenário: CA-INT-02 Revalidar autorização na submissão
    Dado um profissional que abriu o formulário autorizado
    Quando seu vínculo expira ou é revogado antes do POST
    Então a seleção do paciente é rejeitada sem revelar sua existência
    E nenhum arquivo ou recibo de sucesso é produzido

  Cenário: CA-INT-03 Exigir sessão, capacidade, CSRF e confirmação
    Dado um pedido sem sessão, sem capacidade, sem CSRF válido ou sem confirmação
    Quando tenta exportar um paciente
    Então a operação é rejeitada conforme o contrato de rotas e formulários
    E nenhum arquivo ou recibo de sucesso é produzido

  Cenário: CA-INT-04 Respeitar allowlist de campos
    Dado um paciente com CPF, contatos, sexo e histórico clínico preenchidos
    Quando um profissional autorizado exporta seu cadastro
    Então o arquivo contém somente resourceType, id, active, name e birthDate
    E o nome permanece inteiro sem inferência de sobrenome

  Cenário: CA-INT-05 Falhar sem entregar arquivo não auditado
    Dado um pedido autorizado e válido
    Quando a persistência da auditoria falha
    Então não é entregue um attachment
    E a transação do recibo é revertida
    E a resposta não expõe dados clínicos ou traceback

  Cenário: CA-INT-06 Manter exportação exclusivamente online
    Dado que o formulário foi acessado em um dispositivo com PWA
    Quando a conexão é perdida
    Então não é possível exportar um paciente
    E nenhum payload de exportação entra na fila IndexedDB
    E formulário e attachment não aparecem no Cache Storage
