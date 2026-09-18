# Contrato — caixa laboratorial v1

## Dados

`LaboratorySource`: UUID, code CharField(64) unique, label CharField(160), active Boolean default True, operators ManyToMany User. Code/label são identificadores técnicos, sem nome de paciente, credencial ou endpoint. Admin valida texto não vazio após trim e operadores internos. Administração exige staff, profissional interno e permissões nativas. Alterar associação/estado é auditado; não usar sinais genéricos para criar novos grants.

`LaboratoryInboxReceipt`: UUID; source FK PROTECT; received_by FK User PROTECT; received_at auto_now_add; size PositiveInteger; plaintext_sha256(64); ciphertext_sha256(64); ciphertext BinaryField; wrapped_key TextField; encryption_version constante `aegis1`. UniqueConstraint(source, plaintext_sha256); índice (-received_at, -id). `__str__` contém somente tipo/UUID. Sem admin de recibos, delete ou update pela aplicação. Deduplicação não sobrescreve payload, autoria ou timestamp.

AAD exata: `aegisshare:lab-inbox:<UUID>` codificada em UTF-8. Reusar formato retornado por `encrypt_file` sem implementar AES/nonce/wrapping paralelos. Chave mestra nunca armazenada junto ao recibo. Campos criptográficos, hashes e label excluídos da auditoria genérica. Relação M2M de operadores auditada pelo mecanismo já disponível em django-auditlog.

Capacidades no recibo: `interoperability.view_lab_inbox` e `interoperability.receive_lab_file`. Consulta é pré-requisito de upload. Usuário deve ser interno e associado à origem; superusuário usa a regra global Django. Sem concessões automáticas.

## HTTP

Namespace `interoperability`; nomes de URL iguais aos nomes das FBVs.

| Método | URL | FBV | Template |
|---|---|---|---|
| GET | `/interop/laboratorio/` | `lab_inbox_list` | `interop/inbox_list.html` |
| GET/POST | `/interop/laboratorio/receber/` | `lab_inbox_receive` | `interop/inbox_form.html` |
| GET | `/interop/laboratorio/<uuid:pk>/` | `lab_inbox_detail` | `interop/inbox_detail.html` |

Lista aceita somente page e source UUID dentro das origens autorizadas, sem buscar conteúdo/filename/hash. Queryset de lista deve deferir ciphertext, wrapped_key e hashes para não carregar blobs; select_related source/received_by. Um recibo fora de escopo retorna 404, capacidade ausente 403, sem sessão login, método inválido 405.

POST válido ou duplicata autorizada: 302 ao recibo. Campos inválidos: HTML 200. Corpo/arquivo acima do limite: 413 genérico. Falha criptográfica/banco/auditoria: 503 sem detalhes internos. CSRF obrigatório. GET não grava recebimento.

## Form e upload

`LaboratoryInboxForm`: source ModelChoiceField limitado às origens ativas autorizadas; file FileField obrigatório; confirmed BooleanField obrigatório com rótulo “Confirmo o depósito em quarentena; este arquivo não será interpretado nem liberado como resultado”. Sem campo paciente, pedido, amostra, filename ou formato.

Instalar upload handler limitado **somente nesta rota**, antes do parsing multipart/CSRF, com limite agregado de 1 MiB de bytes de arquivos; não depender apenas de `FILE_UPLOAD_MAX_MEMORY_SIZE`, que controla spill para disco, nem de Content-Length. Manter processamento em memória dentro do limite; rejeitar excesso com resposta 413 e sem gravar temporário plaintext. Limitar contagem de arquivos a um. Não desabilitar CSRF para acomodar handler; a instalação precisa ocorrer em middleware antes de CsrfViewMiddleware, instalar o handler antes de ler request.POST/body; o middleware faz o parsing limitado após autorização, mantendo a verificação CSRF posterior.

Após parsing, ler até 1 MiB + 1, verificar vazio, contagem efetiva e tamanho informado pelo objeto de upload. Não chamar decoder, parser ou descompressor. Ignorar nome/extensão/MIME para aceitação semântica: todos os bytes permanecem não confiáveis em quarentena.

## Transação/deduplicação

Validar sessão, profissional e capacidades antes do parsing multipart, com middleware posicionado após Session/Authentication e antes de CSRF; preservar CSRF em todo POST. A origem vem do form: validar associação após o parsing limitado, antes de criptografar ou persistir. Não interpretar o payload durante o parsing. Validar limites antes de criptografar. Em transação curta, bloquear a origem, revalidar ativo/associação/capacidades, consultar a unicidade e gravar sob set_actor. Reenvio permitido somente se origem continuar ativa e autorização vigente; ACCESS auditado, sem novo CREATE.

A constraint é defesa final. Se houver IntegrityError, sair do savepoint que falhou antes de consultar a duplicata; só recuperar recibo que o operador esteja autorizado a consultar. Não converter falha de auditoria em sucesso de deduplicação.

Bytes ficam somente na memória do request e no ciphertext transacional, sem IPFS/Pinata, FileField público ou attachment. Nenhuma chamada de rede dentro da transação.

## Próximo contrato obrigatório

Parsing requer perfil de equipamento real: versão/formato, codificação, framing, mensagens/segmentos permitidos, identificação da origem e sua verificação, correlação pedido/amostra/paciente, terminologias/unidades, estados/correções e erros. A caixa não escolhe esses valores nem constitui uma implementação HL7/ASTM.

No ASGI, limitar os bytes recebidos antes do spool do Django, com corpo máximo de 1.114.112 bytes. O piso de memória do spool deve cobrir esse valor. Resposta antecipada 413 preserva no-store, Vary: Cookie e nosniff.
