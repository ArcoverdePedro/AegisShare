# Extensão 012 — Recebimento laboratorial em quarentena

## Status

**Aprovada explicitamente e implementada em 2026-09-18**, após a proposta de 2026-09-17. Esta é uma etapa de recebimento, não a ingestão clínica necessária à liberação de resultados.

## Contexto

O LIS registra pedidos e coletas; a interoperabilidade exporta cadastro mínimo. Não há perfil institucional de equipamento, versão/formato, identificação, terminologia ou política de resultados definidos para importação.

O recorte permite receber um arquivo opaco em quarentena, guardar bytes cifrados e consultar apenas metadados técnicos. Uma origem cadastrada é declarada pelo operador, não autenticada pelo conteúdo do arquivo. Aceitar o upload não comprova procedência, validade HL7/ASTM, integridade clínica ou vínculo com paciente.

## User stories

- Como operador interno de integração, quero depositar um arquivo recebido de uma origem autorizada, com recibo técnico e sem publicá-lo no prontuário.
- Como operador autorizado, quero reconhecer um reenvio idêntico sem criar cópias nem alterar a autoria do recebimento original.
- Como auditor, quero identificar origem declarada, operador, horário e ações sobre o recibo sem receber conteúdo clínico nos logs.

## Requisitos funcionais

- **RF-INBOX-01:** cadastrar origens técnicas no Admin, com código único, descrição curta, ativo e operadores autorizados. Não criar cadastro de equipamentos clínicos ou regras de parser nesta etapa.
- **RF-INBOX-02:** receber um arquivo por POST autenticado, com CSRF, origem ativa autorizada e confirmação de depósito em quarentena. Nome original, extensão e MIME informados pelo cliente não são prova de formato e não são persistidos.
- **RF-INBOX-03:** limitar conteúdo a **1 MiB (1.048.576 bytes)**, rejeitar vazio e leitura incompleta. Ler no máximo limite + 1 byte, sem confiar em Content-Length/tamanho declarado. Não descompactar, executar, interpretar, normalizar ou converter bytes. Restringir também o upload multipart conforme contrato.
- **RF-INBOX-04:** cifrar bytes usando `encrypt_file()` do Core, com AAD ligada ao UUID do recebimento; guardar ciphertext, chave embrulhada e hashes no banco. A chave mestra permanece na configuração. Erro de criptografia impede o recebimento.
- **RF-INBOX-05:** deduplicar por `(origem, SHA-256 dos bytes exatos)`. Mesmo conteúdo na mesma origem retorna o recibo original após autorização atual; conteúdo diferente ou outra origem representa outro recebimento. Preservar operador/horário originais e auditar o acesso do reenvio. Constraint única cobre concorrência.
- **RF-INBOX-06:** lista paginada de 25 e detalhe mostram somente UUID, código técnico da origem, tamanho, horário, operador e aviso “Em quarentena — conteúdo não validado”. Não mostrar plaintext, hash do plaintext, filename, preview, download ou chave cifrada.
- **RF-INBOX-07:** recibos append-only na aplicação. Criação e auditoria atômicas; falhas não deixam recibo parcial. Auditar leituras apenas dos recibos renderizados, incluindo reenvio. Excluir bytes, chaves e hashes do auditlog genérico.
- **RF-INBOX-08:** exigir profissional interno, capacidade e associação à origem em cada GET/POST. Capacidade de consulta não autoriza envio; ser ADM clínico não concede acesso à caixa. Superusuário segue regra global Django, mas origem deve estar ativa para novos uploads/reenvios. Desativação bloqueia envio e mantém consulta histórica autorizada; revogar associação oculta recibos.

## Requisitos não funcionais

- **RNF-INBOX-01:** duas tabelas de domínio no app existente `apps.interoperability`, Forms, FBVs e templates Django. Sem nova dependência, task queue, parser genérico ou transporte externo.
- **RNF-INBOX-02:** toda rota da caixa `private, no-store`, `Vary: Cookie`, `nosniff`, incluindo erros/redirects/CSRF. Não registrar conteúdo de upload, hashes, nome original ou dados clínicos em logs/relatórios de exceção.
- **RNF-INBOX-03:** fluxo exclusivamente online; sem Cache Storage, fila IndexedDB, WebSocket ou push. Telefone/tablet sem overflow; labels acessíveis e axe sem violações sérias/críticas.
- **RNF-INBOX-04:** validar cópia cifrada, autenticação AAD e rollback com dados sintéticos. Nenhum código de visualização/descarga do payload nesta entrega.

## Autorização e fronteira clínica

Esta caixa possui escopo de **origem técnica**, não de paciente: não identifica nem correlaciona pacientes. Apenas operadores de integração aprovados recebem associação à origem e capacidades. A UI nunca revela conteúdo, mesmo a quem depositou. A futura etapa de parsing deve definir autorização para acessar o plaintext e escopo PEP antes de expor resultados; permissão da caixa não concede acesso clínico.

## Fora de escopo

Parsing HL7/ASTM, verificação de procedência, assinatura, downloads, previews, antimalware como certificação do conteúdo, aprovação/liberação/rejeição clínica, associação a pedido/amostra/paciente, resultados, laudos, correção, expurgo, jobs ou envio a terceiros. Estado é único e constante; não criar workflow nem tabela de eventos sem segundo estado/consumidor.

## Dependências e riscos

Specs 000/005/012/014. Reutilizar criptografia, auditlog e políticas PWA; não reutilizar `IPFSFile` para payload clínico em quarentena, porque a política documental permite compartilhamento e downloads que este recorte proíbe.

Limite por arquivo não limita crescimento agregado: inicialmente apenas piloto sintético restrito, sem ingestão automática. Backup do banco deve preservar configuração de chaves por procedimento separado; perda/rotação incompatível da chave mestra torna ciphertext ilegível. Retenção/expurgo e limites operacionais agregados precisam de decisão antes do uso real. Não afirmar resistência a administrador do banco.

## Aceitação e rastreabilidade

[Cenários](features/lab-inbox.feature), [contratos](contracts/receipt.md), [plano](plan.md), [tarefas](tasks.md). [Evidências executadas](validation.md) e [guia operacional](../../../../docs/caixa-laboratorial.md).

| Requisito | FBV/template implementados | Aceitação |
|---|---|---|
| 01/02/08 | `lab_inbox_receive` / `interop/inbox_form.html`; Admin | CA-INBOX-01/02 |
| 03/04 | mesmo POST / erro seguro | CA-INBOX-03/04 |
| 05/07 | POST e recibo | CA-INBOX-05/06 |
| 06/08 | `lab_inbox_list`, `lab_inbox_detail` / lista/detalhe | CA-INBOX-02/06 |
| RNF-02/03/04 | middleware, caixa e fronteira PWA | CA-INBOX-04/07 |

## Definition of Done

- [x] Proposta, modelo, contratos, plano e cenários preparados.
- [x] Aprovação explícita.
- [x] Implementação, migration reversível, testes de autorização/criptografia/limites/concorrência/auditoria.
- [x] E2E, mobile/axe, privacidade PWA e gates locais com evidências.
- [x] Guia operacional e rastreabilidade para testes reais.
- [ ] Avaliação institucional de uso real, distinta da aprovação técnica do piloto.
