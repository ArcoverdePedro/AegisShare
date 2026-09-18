# Spec 006 — RIS v1: pedidos de imagem

## Status

**Aprovada e implementada em 2026-09-18** pela instrução “[@Ponytail] aprovado, continue”. [Evidências locais](validation.md) e [guia operacional](../../docs/imagem.md).

## Contexto e sequenciamento

O roadmap original coloca LIS, RIS/PACS e centro cirúrgico na fase 3. LIS v1 e recebimento laboratorial cifrado estão implementados; parsing e resultados dependem de perfil real de equipamento. O próximo recorte independente é registrar pedidos de imagem no encontro canônico do PEP.

Esta v1 é **RIS de solicitação**, sem PACS. Não cria `ImagingStudy`, Series ou Report sem imagens/laudos a representar. A aprovação deste recorte inclui o sequenciamento: pedidos primeiro; aquisição DICOM, visualizador e laudos em extensões com contratos próprios.

## User stories

- Como profissional interno autorizado, quero solicitar um exame de imagem de catálogo institucional para um encontro aberto acessível no PEP.
- Como profissional autorizado, quero consultar pedidos e identificar exame solicitado, paciente, encontro, autor e horário, preservando o registro original.
- Como operador, quero repetir um envio interrompido sem duplicar o pedido nem confundir solicitações distintas.

## Requisitos funcionais

- **RF-RIS-01:** catálogo `ImagingExam` com UUID, código técnico único, nome e ativo. Manutenção no Django Admin, por profissional interno staff com permissões nativas. Código/nome obrigatórios, com espaços externos removidos; código sensível a maiúsculas. Não pré-carregar exames, modalidades ou regras clínicas. Não usar dados de paciente nos campos de catálogo.
- **RF-RIS-02:** `ImagingOrder` para um `pep.Encounter` e um exame ativo, com retrato de código/nome, ator e horário definidos pelo servidor. Um exame por pedido. Sem indicação clínica livre, prioridade, contraste, preparo, agendamento ou informações terapêuticas nesta v1.
- **RF-RIS-03:** exigir sessão, `is_internal_professional`, capacidade `ris.view_orders` e `accessible_patients(user)` para qualquer pedido identificável. Criar exige também `ris.order_exam`. Capacidade não cria concessão PEP; papel ADM clínico não dispensa capacidade. Superusuário segue o Django, preservando a regra de profissional interno.
- **RF-RIS-04:** encontro aberto para criar e repetir POST; revalidar escopo, capacidade e encontro dentro da transação. Fechamento bloqueia POST com 409, inclusive retry. Histórico permanece consultável se o paciente continuar acessível. Paciente inativo ou concessão revogada exclui lista/detalhe/criação.
- **RF-RIS-05:** lista paginada de 25 e detalhe, com acesso pelo encontro. Mostrar somente paciente/encontro autorizados, retrato do exame, autor, horário e protocolo. Não indicar realização, estudo disponível ou resultado; todo pedido tem apenas “Solicitado”, sem coluna de estado redundante.
- **RF-RIS-06:** UUID oculto `operation_key`, globalmente único no módulo. Mesmo ator, chave, encontro e UUID de exame retornam o pedido original após autorização atual; preservar retrato/autor/horário e auditar ACCESS. Retry de pedido existente admite exame posteriormente desativado, pois não cria pedido. Mesma chave com outro ator/encontro/exame retorna 409 genérico, sem revelar o pedido conflitante. Nova chave representa nova solicitação, mesmo para o mesmo exame/encontro.
- **RF-RIS-07:** pedido append-only nas entradas da aplicação; sem edição/cancelamento/exclusão e sem Admin de pedido. Alterações do catálogo não alteram o retrato. FKs PROTECT preservam encontro, exame e ator referenciados. Não afirmar proteção contra escrita direta no banco/ORM.
- **RF-RIS-08:** auditar criação, leituras identificáveis e manutenção de catálogo com ator. Criação e auditoria atômicas; falha impede confirmação e reverte pedido. Lista audita apenas pedidos renderizados, após paginação; detalhe e retry auditam ACCESS. Logs/auditlog genérico não copiam nome/código do exame nem nome do paciente; somente identificadores e metadados técnicos necessários.

## Requisitos não funcionais

- **RNF-RIS-01:** app `apps.clinical.ris`, Django Forms, FBVs e DTL. Reusar permissões PEP, usuário, Admin, auditlog, layout e proteção de workflows privados. Sem biblioteca nova, JS próprio, CBV, base genérica de pedidos, fila ou worker.
- **RNF-RIS-02:** respostas em `/imagem/` com `private, no-store`, `Vary: Cookie` e `nosniff`, inclusive login, 403/404/405/409/503 e CSRF. Proteger parâmetros/variáveis sensíveis de relatórios de exceção; erros não incluem identificação do pedido conflitante. Nenhuma API REST/JSON pública.
- **RNF-RIS-03:** somente online. Sem Cache Storage, IndexedDB, fila offline, push ou WebSocket para pedidos de imagem. Uploads DICOM e arquivos da caixa laboratorial não participam deste fluxo.
- **RNF-RIS-04:** telefone/tablet sem overflow horizontal, labels acessíveis, axe sem violações sérias/críticas. Usar `select_related` nas relações renderizadas; não introduzir queries de paciente/exame dentro do loop da lista.
- **RNF-RIS-05:** migration versionada/reversível e concorrência validada no PostgreSQL; testar rollback de auditoria e revogação após abertura do formulário. Não declarar aprovação clínica, CI remoto ou implantação sem evidência.

## Fora de escopo e gates posteriores

DICOM/DIMSE/STOW-RS, PACS/Orthanc/MinIO/S3, viewer Cornerstone, Study/Series/SOP Instance UID, worklist, verificação de identidade de aquisição, imagens/anexos, laudos, assinatura, resultados, cancelamento, correção, contraste, prioridades, preparação, agendamento, cobrança, decisões clínicas ou notificações.

A extensão PACS exige nó interno real, transporte/configuração de rede, identidade e autorização, correlação estudo/pedido/paciente, armazenamento cifrado, retenção/recuperação e contrato do viewer. Laudos exigem modelo/estados institucionais e contrato de assinatura compatível com o gate jurídico do PEP. Não inventar esses valores nem reutilizar a caixa laboratorial como PACS.

`imaging.order.created` consta no roadmap completo; não publicar evento nesta v1 sem consumidor. Uma extensão futura deverá definir payload mínimo, destinatários e publicação após commit, reutilizando `apps.clinical.events.send_after_commit`.

## Rastreabilidade

| Requisito | Superfície implementada | Critério |
|---|---|---|
| 01/07 | Admin de ImagingExam; snapshot do pedido | CA-RIS-01/05 |
| 02/03/04 | `order_create` / `clinical/ris/order_form.html` | CA-RIS-01/02/03 |
| 05/08 | `order_list`, `order_detail` / lista e detalhe | CA-RIS-04/06 |
| 06/07/08 | POST, constraint e lock | CA-RIS-05/06 |
| RNF-02/03/04/05 | middleware, forms, telas e testes | CA-RIS-02/06/07 |

[Contratos](contracts/routes-and-forms.md), [modelo](data-model.md), [plano](plan.md), [tarefas](tasks.md), [aceitação](features/orders.feature) e [inventário de reuso](research.md). Os cenários têm testes executáveis rastreados em [validation.md](validation.md).

## Definition of Done

- [x] Recorte, inventário, modelo, contratos, plano, tarefas e aceitação preparados.
- [x] Aprovação explícita do recorte e sequenciamento RIS/PACS.
- [x] Implementação e migration reversível.
- [x] Testes HTTP, escopo, snapshots, retries, concorrência PostgreSQL e rollback de auditoria.
- [x] E2E/mobile/axe/offline, gates locais e evidências reais.
- [x] Guia operacional e rastreabilidade com nomes reais dos testes.
- [ ] Validação institucional para uso real, distinta de conclusão técnica do piloto sintético.
