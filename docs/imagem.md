# RIS v1 — pedidos de imagem

Spec 006 aprovada e implementada em 2026-09-18. Nível 1/2/3: reuso do projeto, Django nativo e FBVs. O registro é uma solicitação; não comprova realização nem disponibiliza estudo ou laudo.

## Preparar piloto sintético

1. Aplicar migrations, incluindo `ris.0001_initial`.
2. Cadastrar **ImagingExam** no Admin Django existente (`aegis-admin`): código técnico único, nome e ativo. Campos obrigatórios, sem espaços externos; código exato e sensível a maiúsculas. Não colocar dados de paciente no catálogo. Manutenção exige staff, papel interno e permissões nativas de catálogo; nenhum exame clínico vem pré-carregado.
3. Atribuir `ris.view_orders` aos profissionais que consultam; atribuir também `ris.order_exam` aos que solicitam. Papel ADM clínico não substitui capacidades. Superusuário segue permissões globais Django, com requisito de papel interno.
4. Confirmar acesso ao paciente segundo a política PEP existente. Capacidade RIS não concede acesso PEP, nem reativa paciente inativo.
5. Abrir um encontro aberto no PEP e usar **Solicitar imagem**. Selecionar exame ativo e registrar pedido. O menu **Imagem** oferece lista paginada de 25 e detalhe dentro do escopo autorizado.

O pedido guarda retrato do código/nome do exame, ator e horário do servidor. Alterar/desativar catálogo não altera histórico. Pedido é imutável nas entradas da aplicação, sem edição/exclusão no Admin, sem garantia contra escrita direta no banco/ORM.

## Reenvios e erros

Cada formulário possui UUID de operação. Mesmo ator/chave/encontro/exame retorna o pedido original após revalidar autorização e encontro aberto; preserva autoria/horário e audita ACCESS. Exame posteriormente desativado admite apenas esse retry existente. Uma nova chave representa nova solicitação, mesmo para o mesmo exame/encontro; exame inativo não admite pedido novo.

Chave incompatível ou encontro fechado retorna 409 sem revelar pedido conflitante. Fechamento também bloqueia retry; leitura histórica continua permitida no escopo PEP atual. Revogação de concessão ou paciente inativo oculta histórico e impede envio, inclusive formulário já aberto.

Dados inválidos reapresentam formulário preservando chave. Falha de banco/auditoria retorna 503 sem confirmar nem deixar pedido parcial. Consultar histórico antes de repetir: novo GET gera nova chave. Sessão/CSRF/capacidades são obrigatórios.

## Privacidade e retirada

Somente online, sem fila de pedidos, cache de páginas privadas, IndexedDB, push ou WebSocket RIS. Offline não confirma envio. Namespace usa private/no-store, Vary Cookie e nosniff, incluindo erros/redirects/CSRF. Auditoria genérica registra IDs/ator e exclui código/nome do exame e retrato; nomes de paciente não são copiados aos logs RIS.

Usar dados sintéticos até validação institucional. Definir responsáveis, catálogo, gestão de acesso, retenção e recuperação antes de uso real. Retirar capacidades e desativar catálogo para encerrar piloto, preservando pedidos/auditoria. Reverter schema elimina tabelas e só deve ocorrer em banco descartável; rollback operacional de código preserva dados.

Por YAGNI, não há modalidade/contraste/prioridade, preparo, agenda, estudo, imagem, viewer, laudo, assinatura, cobrança ou evento sem consumidor. PACS exige nó interno/protocolo real, correlação, autorização, armazenamento e recuperação. Laudos exigem contrato clínico e jurídico de assinatura; essas extensões não estão aprovadas por esta entrega.

[Evidências e rastreabilidade](../specs/006-ris-pacs/validation.md).
