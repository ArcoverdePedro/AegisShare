# Cadastro funcional — Spec 010 v1

Nível 1/2/3: reuso do CustomUser, Django Admin/ModelForm e duas FBVs. O cadastro é informativo: não confirma vínculo, admissão, escala, habilitação, treinamento ou relação trabalhista.

## Ativação e permissões

Aplicar `hr.0001_initial` pelo procedimento de atualização existente. Conceder explicitamente `hr.view_employee` aos profissionais internos autorizados a consultar **todos** os perfis, ativos e inativos. Para manutenção no Admin, o usuário também precisa ser staff e ter `hr.add_employee` ou `hr.change_employee`. Papel ADM não substitui capacidade; superusuário continua sujeito ao requisito de papel interno. Não há grants automáticos nem escopo por setor.

A consulta institucional inclui nomes atuais, username, setor, função e estado cadastral. Não concede autoacesso ao titular. Validar institucionalmente finalidade, necessidade de acesso e conteúdo antes de usar dados reais. Se a instituição exige segregação por setor, matrícula ou auditoria ACCESS de toda leitura no Admin, aprovar uma extensão antes desse uso.

## Cadastro

O Django Admin de **Cadastro funcional** cria um perfil para usuário ativo ADM/FUNC ainda sem Employee. Informar setor e função, até 120 caracteres; espaços externos são removidos. Na edição, o username associado aparece somente para leitura. Para retirar um perfil de novos usos administrativos, desmarcar **Cadastro ativo**; não há exclusão individual ou em lote.

Employee.active não altera user.is_active, login, papel, staff, superusuário, grupos, capacidades ou grants PEP. Usuário posteriormente inativado ou reclassificado mantém o perfil histórico e continua visível ao operador RH autorizado. Nome exibido vem do User atual; não é snapshot histórico. Alterar Employee não certifica habilitação clínica e não modifica outros módulos.

CustomUser segue como fonte de identidade, nomes, contato e autenticação. Não copiar CPF, email, telefone, senha ou campos RBAC para Employee. Um usuário possui no máximo um perfil; a constraint OneToOne protege criação concorrente.

## Consulta e auditoria

**RH** abre `/rh/funcionarios/`, lista 25 perfis por página e mostra detalhes por UUID Employee. Usuários internos sem Employee não aparecem como cadastrados. Todas as leituras nessas duas FBVs geram ACCESS somente para os registros renderizados; falha de auditoria bloqueia entrega.

Criação/alteração no Admin registra auditlog com ator e Admin LogEntry na mesma transação; falha reverte a mutação e retorna erro genérico. Auditlog não copia setor/função e object_repr contém apenas tipo/UUID. O Admin nativo não emite ACCESS em suas leituras de lista/formulário ou na seleção de usuários; essa é a fronteira aprovada nesta v1, sem declaração de auditoria administrativa integral.

Todas as rotas RH e EmployeeAdmin são private/no-store, Vary Cookie e nosniff. POST Admin usa CSRF nativo e dados sensíveis de exceções são protegidos. Revogar view_employee bloqueia consulta e salvamento Admin já aberto; revogar change_employee bloqueia edição, preservando consulta autorizada.

## Online, retirada e limites

Fluxo exclusivamente online: páginas/forms/payloads RH não entram em Cache Storage, IndexedDB, fila, sync ou push. Para retirada, revogar capacidades e preservar perfis/auditoria. Rollback de código mantém dados; reversão do schema somente em banco descartável ou com procedimento prévio de preservação.

Guarda de associação/exclusão vale para entradas contratadas da aplicação; SQL/ORM direto permanece fora dessa promessa. Sem Shift, TimeClock, Training, calendário, ponto, folha, documentos, biometria, geolocalização ou eventos. Esses fluxos exigem contratos institucionais próprios.

[Spec e critérios](../specs/010-rh-escalas/spec.md) · [Evidências](../specs/010-rh-escalas/validation.md).

## Registro profissional e ausências (H26)

No Admin (`EmployeeAdmin`): conselho, número e UF do registro (exigidos juntos), validade e especialidade. Ausências (férias, licença/afastamento, outro) são lançadas inline com início e fim (constraint `fim >= início`); não registram motivo de saúde. Efeito atual: a agenda (H11) recusa abrir horários e agendar no período de ausência. Registro vencido aparece como "vencido" no detalhe, sem bloquear atos — o efeito sobre prescrição/assinatura depende de G01/G06. Escalas, trocas de plantão, ponto e folha não estão implementados (aguardam G01).
