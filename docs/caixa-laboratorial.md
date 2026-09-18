# Caixa laboratorial em quarentena

Extensão da Spec 012 aprovada e implementada em 2026-09-18. Nível 1/2/3: reuso do Core, Django nativo e FBVs. Este recorte recebe bytes opacos; não valida HL7/ASTM nem produz resultados LIS.

## Preparar um piloto sintético

1. Aplicar migrations, incluindo `interoperability.0002_laboratorysource_laboratoryinboxreceipt`.
2. Manter `FILE_ENCRYPTION_KEY` válida, de 32 bytes, conforme a configuração criptográfica do Core. Banco e chaves precisam de backups separados e recuperação ensaiada; não trocar a chave sem política compatível de rotação.
3. No Admin Django, cadastrar **LaboratorySource** com código técnico único, descrição técnica, origem ativa e operadores internos. Nunca incluir nome, prontuário ou outro identificador de paciente nesses campos.
4. Atribuir `interoperability.view_lab_inbox` para consulta; para envio, atribuir também `interoperability.receive_lab_file`. Associação à origem continua obrigatória. O acesso ao Admin depende das permissões nativas, staff e papel interno; ser ADM clínico não concede capacidades da caixa. Superusuário segue as regras globais Django.
5. Abrir “Caixa laboratorial” no menu clínico, selecionar origem, enviar um arquivo de até **1 MiB** e confirmar depósito. O recibo informa protocolo, origem declarada, tamanho, operador e horário. O conteúdo permanece cifrado e não tem preview ou download.

Um reenvio dos mesmos bytes à mesma origem retorna o recibo original e audita ACCESS, preservando autoria/horário. Outra origem ou bytes diferentes geram outro recibo. Desativar origem impede novos envios e reenvios; a consulta histórica continua autorizada. Remover associação oculta seus recibos. Falhas de persistência/criptografia/auditoria não confirmam o upload; consultar recibos antes de repetir.

## Limites e privacidade

Um arquivo por requisição, conteúdo até 1.048.576 bytes e corpo multipart até 1.114.112 bytes. A contagem usa bytes lidos. O handler da rota usa somente memória; o limite ASGI atua antes do spool do Django. O piso de memória do spool cobre o corpo permitido, inclusive se a configuração documental for menor, sem aumentar limites de aceitação de arquivos documentais. Nome original e MIME não são persistidos nem interpretados. Configurar limites compatíveis também no proxy e no servidor HTTP, cujos buffers estão fora da aplicação Django.

A lista pagina 25 recibos. As consultas de metadados excluem ciphertext, chave embrulhada, hashes e descrição da origem. A auditoria de recibos exclui os campos criptográficos; cadastros e associações de operadores são auditados. Recibos são imutáveis nas entradas da aplicação, sem promessa de resistência a administrador do banco ou escrita direta pelo ORM.

As páginas e erros usam `private, no-store`, `Vary: Cookie` e `nosniff`. Exige conexão: não há fila, Cache Storage ou IndexedDB para arquivos/recibos. Upload offline não confirma recebimento.

## Operação posterior

Antes de dados reais: decidir operadores/origens autorizados, retenção/expurgo, capacidade agregada, monitoramento, chaves e recuperação. O limite individual não limita crescimento total do banco. Para retirar o piloto, revogar capacidades e desativar origens, preservando recibos e auditoria. Reverter migration elimina tabelas e só deve ocorrer em banco descartável.

Parsing e resultados exigem perfil real de equipamento, formato/codificação, verificação de procedência, correlação paciente/pedido/amostra, terminologias/unidades e políticas clínicas. A caixa não escolhe esses valores. Sem parser, worker, dependência nova, evento ou endpoint de decifração nesta entrega, por YAGNI.

[Evidências locais](../specs/012-interoperabilidade/extensions/lab-inbox/validation.md).
