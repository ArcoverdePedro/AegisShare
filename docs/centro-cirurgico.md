# Centro Cirúrgico v1 — solicitações de procedimentos

Spec 007 autorizada e implementada em 2026-09-18. Nível 1/2/3: reuso dos padrões existentes, Django nativo e FBVs. O registro é somente uma solicitação; não agenda, autoriza clinicamente nem confirma realização de cirurgia.

## Preparar um piloto sintético

1. Aplicar migrations, incluindo `surgery.0001_initial`.
2. No Admin Django existente (`aegis-admin`), cadastrar **Procedure** com código técnico único, nome e ativo. Campos obrigatórios, sem espaços externos; código exato e sensível a maiúsculas. Sem procedimentos clínicos pré-carregados e sem dados de paciente no catálogo. Manutenção exige staff, papel interno e permissões nativas de catálogo.
3. Atribuir `surgery.view_cases` para consulta e também `surgery.request_procedure` para criação. Ser ADM clínico não dispensa capacidades; superusuário segue Django, com requisito de papel interno. Confirmar o escopo PEP: essas capacidades não concedem acesso a pacientes.
4. Abrir um encontro OPEN acessível no PEP e usar **Solicitar procedimento**. Selecionar procedimento ativo e **Registrar solicitação**. Menu **Centro Cirúrgico** oferece lista paginada de 25 e detalhe autorizado.

A solicitação guarda protocolo, encontro, retrato de código/nome do procedimento, autor e horário do servidor. Exibe “Solicitação registrada — sem agendamento ou autorização cirúrgica”. Paciente vem do encontro, sem cadastro duplicado. Alteração/desativação do catálogo não muda histórico.

## Reenvios e erros

O formulário possui UUID de operação. Mesmo ator/chave/encontro/procedimento retorna original após revalidar autorização e encontro aberto, preservando retrato/autoria/horário e auditando ACCESS. Procedimento posteriormente desativado admite somente retry existente. Nova chave é nova solicitação, mesmo para o mesmo procedimento/encontro; exige procedimento ativo.

Encontro fechado bloqueia novo envio e retry com 409; leitura histórica continua permitida no escopo PEP atual. Chave incompatível retorna conflito sem identificar a solicitação original. Revogar concessão ou desativar paciente oculta histórico e impede envio, inclusive formulário já aberto.

Entrada inválida reapresenta formulário preservando chave. Falha de banco/auditoria retorna 503 e não confirma nem deixa registro parcial. Consultar histórico antes de repetir: abrir novo formulário gera nova chave. Sessão/CSRF e capacidades são obrigatórios.

## Privacidade e retirada

Exclusivamente online. Sem cache de telas privadas, fila offline/IndexedDB, push, WebSocket ou eventos cirúrgicos; tentativa offline não confirma registro. Namespace privado/no-store, Vary Cookie e nosniff, incluindo erros, redirects e CSRF. Auditoria genérica exclui código/nome/retrato do procedimento e não copia nome de paciente. Lista audita somente itens renderizados após paginação; falha de auditoria de leitura impede entrega identificável.

Solicitações sem edição/exclusão nas entradas da aplicação ou Admin, sem garantia contra escrita direta no banco/ORM. Usar dados sintéticos até validação institucional, definindo responsáveis, catálogo, acesso, retenção e recuperação. Retirada revoga capacidades/desativa catálogo e preserva solicitações/auditoria. Reverter schema apaga tabelas e só deve ocorrer em banco descartável; rollback operacional de código preserva dados.

Por YAGNI, sem SurgicalSchedule/Material, diagnóstico/risco/anestesia/consentimento, salas/equipes, agenda, execução, checklist, recuperação, cobrança ou assinatura. Mapa exige contrato operacional de recursos/intervalos/conflitos; materiais dependem da Spec 009 sem estoque paralelo; execução/checklist/recuperação e assinatura precisam de contratos institucionais próprios.

[Evidências e rastreabilidade](../specs/007-centro-cirurgico/validation.md).
