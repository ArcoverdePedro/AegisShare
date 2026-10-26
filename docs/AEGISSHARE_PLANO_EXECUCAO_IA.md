# AegisShare — plano completo de execução para agente de IA

> Objetivo: concluir um HIS de código aberto para o escopo hospitalar aprovado, aproveitando o código existente.
> Repositório: https://github.com/ArcoverdePedro/AegisShare
> Base inspecionada: master, commit 38c6100d54d9bbf45e18e4e8af1bdf73b13954e5, em 26/10/2026.
> Natureza: roteiro de implementação; a análise de origem foi estática. O agente deve verificar o checkout atual.
> Estratégia de tokens: ler o núcleo abaixo uma vez por sessão; depois, somente o cartão ativo e suas referências.

## 00 — Instrução de execução e leitura econômica

Você deve IMPLEMENTAR este plano, validar o resultado e continuar nas tarefas elegíveis. Entregar apenas recomendações ou concluir uma primeira tarefa não encerra o trabalho autorizado.

1. Na primeira sessão, leia AGENTS.md aplicáveis, esta seção, 01–05 e H00. Depois, leia somente o cartão escolhido, as decisões pertinentes e o código necessário.
2. Nas sessões seguintes, leia esta seção, o checkpoint e o cartão ativo. Consulte novamente as regras comuns somente quando necessário. Não recarregue o plano inteiro.
3. Trabalhe no checkout real. Confirme branch, commit e alterações existentes. Preserve trabalho alheio; use branch/worktree quando apropriado.
4. Execute a menor tarefa elegível, sem dependência ou decisão impeditiva. Termine um fluxo vertical: dados, validação, autorização, interface, histórico e testes.
5. Continue automaticamente na próxima tarefa elegível. Um bloqueio local não interrompe trabalho independente.
6. Decida detalhes técnicos reversíveis usando o código, AGENTS.md e Django. Solicite somente informações realmente ausentes ou decisões externas que mudem segurança, significado clínico, obrigação jurídica ou contrato financeiro.
7. Não interprete “fora do escopo da v1” como proibição eterna: este plano solicita extensões. Atualize os contratos afetados. Preserve os gates de governança clínica/jurídica expressamente pendentes.
8. Não habilite uso real, faturamento externo, assinatura válida ou automação clínica com mocks, dados sintéticos ou aprovação presumida.
9. Preserve o monólito Django, FBVs, forms, templates e regras reutilizáveis existentes. A ADR-0004 continua válida: sem nova API REST pública do AegisShare. Integrações podem usar clientes de saída, arquivos e processamento interno autenticado.
10. Use um agente por padrão. Delegação, infraestrutura adicional e dependências exigem benefício concreto e autorização compatível com o ambiente.
11. Não faça publicação, merge, envio a terceiros ou operação com dados reais sem autorização correspondente já existente. Isso não impede implementação local, testes sintéticos ou preparação de entrega revisável.
12. Ao encerrar uma sessão, grave checkpoint conciso e indique a próxima ação exata. Nunca declare o sistema completo com requisito obrigatório bloqueado.

Economia operacional:

- Primeiro rg --files e rg -n; depois trechos delimitados. Não imprimir árvore inteira, lockfile, minificados, dumps ou logs de sucesso.
- Agrupar leituras independentes; manter edição, migração e verificação dependentes em sequência.
- Reutilizar descobertas e evidências válidas da sessão. Reler somente após mudança relevante.
- Executar primeiro os testes afetados. Rodar a suíte completa nos marcos definidos, sem repeti-la sem causa.
- Não gerar documentação repetida, abstrações especulativas, testes de getters triviais ou planos paralelos.
- Respostas de rotina: até 6 linhas com tarefa, mudança, teste, bloqueio e próxima ação. Expandir somente para falha ou decisão relevante.
- Descrever resultados e evidências; não narrar cada comando.
- Economia de tokens nunca justifica omitir validação crítica, suprimir erro ou inventar execução.

Localização por marcador, sem leitura integral:

~~~bash
rg -n '^## |^### H[0-9][0-9]' AEGISSHARE_PLANO_EXECUCAO_IA.md
# Depois use sed -n 'INICIO,FIMp' para o trecho necessário.
~~~

## 01 — Escopo e resultado exigido

Alvo inicial: hospital geral brasileiro com recepção/ambulatório, urgência quando oferecida, internação, prescrição/farmácia, enfermagem, diagnóstico, materiais, compras e faturamento. Ativar somente serviços existentes na instituição. Particular, convênios e SUS são trilhas de faturamento distintas; selecionar as aplicáveis.

Sem resposta sobre G01, usar esse alvo como escopo provisório de desenvolvimento sintético. Prosseguir nas partes técnicas reversíveis que independem da escolha; manter a decisão e a liberação operacional pendentes. Não repetir a mesma pergunta em cada cartão.

“Completo” significa completar e homologar as jornadas do escopo aprovado, incluindo exceções, recuperação e integrações necessárias. Não significa atender silenciosamente toda especialidade hospitalar possível.

Entregar por requisito aplicável:

- Código funcional integrado, migrations seguras, permissões e interface utilizável.
- Contratos e testes do comportamento, incluindo falhas plausíveis.
- Histórico, autoria, rastreabilidade e preservação dos dados existentes.
- Configuração e procedimento operacional necessários à implantação.
- Evidência reproduzível e pendências explícitas, sem funcionalidades fictícias.

Gates do escopo não escolhido não autorizam excluir trabalho por conveniência. Registrar N/A somente com justificativa e confirmação do responsável pelo escopo.

## 02 — Baseline e mapa de leitura

Já existe; verificar e ampliar antes de recriar:

| Domínio | Ponto inicial |
| --- | --- |
| Identidade, encontros e evolução | apps/clinical/pep/{models,forms,views,permissions}.py; specs/001-pep/ |
| Alergias propostas | specs/001-pep/extensions/allergy-intolerance/ |
| Leitos e movimentos | apps/clinical/adt/; specs/002-adt/ |
| Prescrição, revisão, lotes e dispensação | apps/clinical/prescription/; specs/003-prescricao-farmacia/ |
| Sinais vitais e administração | apps/clinical/nursing/; specs/004-enfermagem/ |
| Pedidos e coleta laboratorial | apps/clinical/lis/; docs/laboratorio.md |
| Pedidos de imagem | apps/clinical/ris/; docs/imagem.md |
| Solicitações cirúrgicas | apps/clinical/surgery/; docs/centro-cirurgico.md |
| Preparação manual de contas | apps/admin/billing/; docs/faturamento.md |
| Materiais e requisições | apps/admin/inventory/; docs/estoque-requisicoes.md |
| Cadastro funcional | apps/admin/hr/; docs/cadastro-funcional.md |
| FHIR mínimo e caixa laboratorial | apps/interoperability/; docs/interoperabilidade.md; docs/caixa-laboratorial.md |
| Solicitações do titular | apps/compliance/; docs/solicitacoes-titular.md |
| Arquivos, segurança e PWA | aegis_share/; apps/pwa/; SECURITY.md |
| Configuração e validação | pyproject.toml; mysite/settings*.py; .github/workflows/django.yml; tests/e2e/ |

A base já usa AGPL-3.0-only, controle de acesso, auditoria, transações, idempotência e testes. Algumas especificações concluídas cobrem apenas v1 reduzida. Confirmar capacidades pelo fluxo real; nome de app ou checkbox antigo não prova a entrega deste plano.

A cópia usada na análise pode estar incompleta e não substitui um checkout íntegro.

## 03 — Contrato comum de implementação e conclusão

Aplicar a todos os cartões; não repetir esta lista nas implementações.

**Identidade e escopo.** Patient, Encounter e usuário são canônicos. Reutilizar grants, capacidades e escopo autorizado; RBAC deve incluir ação e acesso ao objeto. Filtrar listas, detalhes, seletores, exportações, arquivos e POSTs. Papel cliente não recebe acesso clínico interno por reutilização acidental.

**Dados e estados.** Definir estados, transições, invariantes e exceções antes da mutação. Preservar fatos anteriores por adendo, versão, cancelamento ou estorno auditável. Preferir constraints de banco para invariantes concorrentes. Não alegar inviolabilidade contra administrador do banco apenas por sobrescrever save/delete.

**Concorrência.** Usar transação para efeitos inseparáveis, bloqueio/constraint quando necessário e chave idempotente em operações sensíveis. Mesma chave/conteúdo compatível recupera a operação; colisão incompatível falha sem vazar dados. Não deduplicar atos clínicos apenas por aparência semelhante.

**Integração.** Evitar HTTP externo dentro de transação longa. Registrar estado persistente de envio/recebimento, correlação, timeout, retry limitado e reconciliação. Persistir antes de confirmar; repetir não duplica efeito. Sem “sucesso” fabricado quando o provedor está indisponível.

**Interface.** FBV + Form/ModelForm + templates; aproveitar HTMX existente quando útil. Validar no servidor. GET sem efeitos; POST com CSRF e redirect quando adequado. Interfaces essenciais acessíveis em telefone/tablet; botões e telas operacionais devem cobrir as exceções.

**Privacidade.** Respostas clínicas private/no-store; logs/eventos/push minimizados. Proteger anexos, exportações e erros. Manter a fronteira PWA: apenas nursing.vitals.record está liberado offline. Ampliar offline exige contrato específico; medicação, ADT e dispensação continuam online.

**Domínio clínico.** Não inventar protocolos, limiares, doses, terminologias, compatibilidades, diagnósticos ou decisões assistenciais. Registrar procedência e versão do conteúdo aprovado. Desconhecido não significa normal, negativo ou seguro. Revisão farmacêutica, autorização administrativa e assinatura jurídica são eventos distintos.

**Desempenho.** Paginar; filtrar/agregar no banco; evitar N+1 em view, form e template. Medir consultas críticas. Preservar Decimal e unidades explícitas; nunca calcular dinheiro com float nem converter dose/embalagem sem regra aprovada.

**Evolução.** Adicionar migrations compatíveis com dados legados. Quando houver backfill, definir mapeamento, contagem antes/depois e validação. Preferir expansão → migração de dados → contração posterior. Rollback operacional deve preservar dados; não prometer reversibilidade quando ela não existe.

**Definition of Done — DoD.** O cartão termina somente com:

1. Fluxo e aceites implementados, incluindo capacidades, escopo e interface.
2. Testes relevantes aprovados, migrations consistentes e nenhum erro introduzido nas verificações aplicáveis.
3. Exceções, retries, concorrência e histórico testados quando pertinentes.
4. Ausência de vazamento nos caminhos afetados, com teste das fronteiras alteradas.
5. Integração com consumidores existentes e compatibilidade dos registros legados.
6. Contratos/documentação operacional atualizados no local já usado pelo módulo.
7. Evidência associada ao commit; pendências ou limitações registradas com precisão.

Teste compartilhado mínimo: caminho permitido, acesso negado/objeto fora do escopo, entrada inválida, transição indevida, duplicação e falha parcial quando aplicáveis. Não criar teste repetitivo sem regra verificável.

## 04 — Decisões externas e governança

Manter um registro conciso em docs/his/DECISOES.md, referenciando a spec afetada. Cada decisão: ID, pergunta, responsável, alternativas concretas, impacto, decisão, data, versão e evidência. Usar sintéticos para preparar propostas e testes; não registrar aprovação humana inexistente.

| Gate | Decisão necessária | Quem deve validar |
| --- | --- | --- |
| G01 | Serviços, unidades, perfis, número de instituições e trilhas de faturamento | Direção/produto e operação |
| G02 | Identificação de paciente, desconhecidos, duplicidades, responsáveis e acessos emergenciais | Cadastro, assistência e privacidade |
| G03 | Terminologia/estados de alergia e elegibilidade para checagem | Responsável clínico e farmácia |
| G04 | Fonte, licença e conteúdo de Interaction/DoseRule; peso elegível e sua atualidade | Governança clínica/farmacêutica |
| G05 | Documentos assináveis, padrão de assinatura, credenciais, guarda e validação | Responsáveis jurídico, clínico e técnico |
| G06 | Aprazamento, exceções de medicação, cuidados, triagem e alertas clínicos | Enfermagem, medicina e farmácia |
| G07 | Catálogos, resultados críticos, laudos, equipamentos e procedimentos de diagnóstico | Laboratório e imagem |
| G08 | Regras cirúrgicas, anestésicas, checklists, consentimentos e recuperação | Centro cirúrgico e responsáveis assistenciais |
| G09 | Unidades/conversões, autorizações, tabelas, impostos e momento da cobrança | Suprimentos, financeiro e contratos |
| G10 | Retenção, bases legais, titulares, fornecedores e incidentes | Controlador/encarregado e jurídico |
| G11 | Infraestrutura, credenciais, parceiros, restauração e metas operacionais | Operação e responsáveis externos |

Gates conhecidos da base: T-PEP-08; T-ALLERGY-02/03/04/05; T-RX-02/17; T-NUR-09/11. Conferir situação atual antes de tratar como bloqueado.

Se uma aprovação for exigida antes do próprio model/contrato, preparar a decisão e testes de contrato possíveis; não criar o model por antecipação. Se só a ativação depender dela, implementar a parte autorizada e mantê-la desabilitada. Avançar em cartões independentes. Não pedir confirmação para cada escolha técnica rotineira.

## 05 — Progresso, dependências e ordem

Criar docs/his/PROGRESSO.md apenas se não houver checkpoint equivalente. Manter um índice curto, sem copiar os cartões:

~~~text
Base: <commit> | Escopo: <G01>
ID | Estado | Evidência/commit | Bloqueio ou próxima ação
Última verificação: <comando + resultado>
Próxima tarefa: <ID e primeiro passo>
~~~

Estados: TODO, DOING, DONE, READY, BLOCKED, N/A.

- DONE: DoD e aceites completos, com decisões necessárias resolvidas.
- READY: código tecnicamente validado em ambiente sintético; falta integração real ou homologação indicada.
- BLOCKED: dependência/decisão ausente impede parte obrigatória; registrar exatamente qual.
- N/A: fora do escopo confirmado, com referência à decisão.
- READY e BLOCKED não contam como entrega hospitalar homologada.

Manter incrementos pequenos e coesos, com rastreabilidade por cartão. Não misturar todos os módulos em uma mudança indivisível; continuar a sequência sem transformar cada incremento em uma nova solicitação de autorização.

Ordem recomendada; dependências podem permitir avanços independentes:

| Etapa | Cartões |
| --- | --- |
| Base e contratos | H00–H03 |
| PEP e proteção transversal | H04–H07, H27–H30 |
| Assistência e operação | H08–H13, H26 |
| Diagnóstico e cirurgia | H14–H18 |
| Suprimentos e receita | H19–H25 |
| Gestão e extensões | H31–H33 |
| Distribuição e homologação | H34–H35 |

“Dep” indica pré-requisito do trecho correspondente. Não bloquear um cartão inteiro se somente sua integração final depender de outro; entregar a parte independente e registrar o restante.

## 06 — Cartões de implementação

### H00 — Confirmar baseline e executar diagnóstico inicial

Dep: nenhuma.

- Conferir checkout íntegro, AGENTS.md locais, dependências, settings, rotas, migrations e testes existentes. Comparar cada capacidade deste plano com o código atual; não refazer trabalho já concluído.
- Preparar ambiente descartável, nunca apontando testes ao banco real. Usar versões e lockfile do projeto.
- Executar checks iniciais uma vez; registrar falhas preexistentes separadamente.
- Aceite: baseline reproduzível, mapa de capacidades corrigido e checkpoint com próxima tarefa elegível.

### H01 — Fechar escopo e contratos incrementais

Dep: H00. Gate: G01.

- Mapear jornadas, atores, unidades, serviços e faturamento aplicáveis. Declarar explicitamente especialidades incluídas/excluídas.
- Reutilizar specs/000–014 e ADRs; criar extensão curta quando o comportamento novo exceder a v1.
- Para cada incremento definir entrada, saída, permissão, estados, exceções, consumidores e aceites. Não criar uma segunda documentação paralela.
- Aceite: escopo verificável e decisões pendentes identificadas por gate; trabalho técnico independente pode prosseguir.

### H02 — Consolidar capacidades, vínculos e escopos

Dep: H01. Gates: G01/G02.

- Mapear recepção, médico, enfermagem, farmácia, diagnóstico, faturamento, suprimentos, RH e auditoria a capacidades explícitas; separar administração técnica de privilégios assistenciais.
- Reutilizar PatientAccessGrant, acessos ADT e permissões atuais; suportar vínculos de equipe/unidade quando aprovados.
- Se houver várias instituições na mesma instância, implementar isolamento consistente antes de compartilhar dados; workspaces de documentos não equivalem a tenant clínico.
- Definir acesso emergencial justificado, temporário e revisável se exigido; resolver consulta histórica de pacientes inativos por capacidade própria.
- Aceite: matriz testada em listas, detalhes, ações, arquivos e exportações, incluindo revogação e acesso cruzado.

### H03 — Completar identificação e cadastro do paciente

Dep: H02. Gate: G02.

- Ampliar identificação canônica para múltiplos identificadores com tipo/emissor, CNS quando aplicável, contatos, endereço, responsáveis e nome social conforme contrato.
- Suportar paciente sem documento/desconhecido com identidade provisória rastreável. Não usar CPF fictício nem duplicar Patient por módulo.
- Detectar possíveis duplicidades; permitir conciliação/mesclagem somente por procedimento autorizado, preservando IDs históricos, referências e auditoria.
- Aceite: cadastro provisório pode ser regularizado; homônimos não são unidos automaticamente; legados permanecem vinculados e pesquisáveis.

### H04 — Completar o PEP estruturado

Dep: H03. Gates: conteúdo clínico pertinente.

- Acrescentar lista de problemas/diagnósticos, antecedentes, procedimentos, reconciliação medicamentosa, registros multiprofissionais e resumo de alta.
- Usar terminologias/catálogos aprovados, com origem/versão; registrar autor, encontro e tempo clínico. Não extrair diagnóstico automaticamente de texto livre.
- Preservar evolução/adendos existentes e integrar pedidos, resultados, prescrição e enfermagem à visão longitudinal.
- Aceite: paciente tem histórico coerente entre encontros; correções preservam versões; fechamento não permite alteração clínica indevida; alta reúne informações aprovadas.

### H05 — Implementar alergias e intolerâncias

Dep: H04. Gate: G03; respeitar a extensão já escrita.

- Resolver T-ALLERGY-02 antes de executar partes dependentes. Implementar modelo, migrations, forms, views, histórico e auditoria aprovados.
- Distinguir fonte desconhecida/não revisada, revisão registrada e alergia ativa/verificada; registrar substância, reação, estados, origem e autoria.
- Integrar somente registros elegíveis ao RX e registrar a versão consultada na revisão.
- Aceite: ausência de registro nunca vira “sem alergias”; correção mantém fato anterior; checagem indisponível permanece explícita.

### H06 — Implementar assinatura e documentos clínicos

Dep: H04. Gate: G05.

- Resolver T-PEP-08 por documento/uso. Preservar bytes/conteúdo e versão assinados, signatário, horário, algoritmo/provedor e evidências de validação pertinentes.
- Implementar assinatura, verificação, expiração/revogação e tratamento de falha conforme padrão aprovado; adendo gera nova versão sem alterar a assinada.
- Não tratar hash, nome digitado, TOTP ou revisão farmacêutica como assinatura jurídica.
- Aceite: conteúdo alterado falha na verificação; autoria e vínculo são verificáveis; credencial indisponível não produz documento “assinado”. Mock/certificado sintético não comprova validade para uso real.

### H07 — Completar referências e revisão de segurança da prescrição

Dep: H04/H05 no trecho que consome alergias. Gates: G03/G04.

- Resolver T-RX-02 e T-NUR-09: procedência, licença, versão, aprovação e revogação de referências; origem/atualidade do peso e demais fatos.
- Preservar avaliação determinística, findings e revisão humana; ampliar regras somente com dados/fontes aprovados.
- Invalidar ou exigir nova revisão quando prescrição, fatos relevantes ou referências mudarem conforme contrato.
- Aceite: referência ausente, vencida, não aprovada ou fato inelegível resulta em indisponibilidade explícita; testes sintéticos não são promovidos a catálogo clínico de produção.

### H08 — Completar o ciclo medicamentoso

Dep: H04; H07 para alertas automatizados. Gate: G06.

- Evoluir frequência/duração para aprazamento governado, doses previstas, início/fim, suspensão, substituição e reconciliação na admissão/transferência/alta.
- Integrar ordem validada, dispensação por lote e administrações; preservar as entidades e serviços existentes.
- Tratar devolução, perda e estorno de estoque por movimentos vinculados, mantendo fonte de verdade única.
- Aceite: mudança de prescrição não altera administrações passadas nem gera dose duplicada; dispensação e saldo conciliam sob concorrência; conversões não aprovadas são recusadas.

### H09 — Completar cuidados e registros de enfermagem

Dep: H04. Gate: G06.

- Acrescentar avaliação, plano/prescrição de cuidados, execução/evolução, balanço hídrico, dispositivos e passagem de plantão conforme serviços.
- Integrar sinais vitais existentes, proveniência e correções. Alertas e classificações clínicas dependem de protocolos aprovados.
- Exibir pendências por paciente/turno com responsáveis e histórico; não ampliar offline implicitamente.
- Aceite: cuidado planejado, realizado e corrigido é rastreável; unidades, períodos e balanços são coerentes; troca de turno conserva pendências.

### H10 — Completar administração e exceções de medicação

Dep: H08/H09 nos trechos usados. Gate: G06; resolver T-NUR-11.

- Modelar estados aprovados para administrada, recusada, omitida, atrasada, parcial e divergente; vincular dose prevista, prescrição, dispensação/lote e responsável.
- Registrar motivo, horários e correção auditável; distinguir tentativa, ocorrência e administração efetiva.
- Implementar identificação positiva e dupla checagem quando exigidas, sem pressupor que ler código de barras prova administração.
- Aceite: retries não duplicam dose; recusa/omissão não contam como administrada; exceção não modifica automaticamente a prescrição; fluxo permanece online.

### H11 — Implementar recepção, agenda e filas ambulatoriais

Dep: H02/H03; integrar H26. Gate: G01.

- Agenda por profissional/recurso/unidade com duração, disponibilidade, bloqueio, encaixe autorizado, remarcação, cancelamento e falta.
- Fluxo de chegada/check-in, fila e chamada vinculados ao encontro canônico; identificação de paciente preservada.
- Confirmações externas somente com canal autorizado e conteúdo mínimo; sem credenciais fictícias.
- Aceite: reservas simultâneas respeitam capacidade; remarcação preserva histórico; fila não expõe dados clínicos em painel público; não há calendário paralelo incompatível com RH/cirurgia.

### H12 — Implementar urgência e classificação de risco

Dep: H11/H09 nos trechos usados. Gate: G06 e inclusão do serviço.

- Registrar chegada, queixa, classificação por profissional, reavaliação, encaminhamento, observação e desfecho; integrar encontro e ADT.
- Usar protocolo institucional versionado; ordem operacional manual deve funcionar quando automação não estiver aprovada.
- Registrar tempos e mudanças de prioridade com motivo. Não inferir triagem por IA ou por limiares inventados.
- Aceite: classificação não equivale a diagnóstico; reavaliação mantém histórico; transferências/alta conciliam os estados e a fila.

### H13 — Completar a operação de leitos e alta

Dep: H02/H03; aproveitar ADT existente. Gate: G01/G02.

- Acrescentar solicitação/reserva, preparação/higienização, liberação, bloqueio justificado, isolamento e previsão de alta conforme contrato.
- Separar estado operacional, ocupação e reserva; definir transições e responsáveis.
- Integrar alta clínica, documentos, reconciliação medicamentosa e liberação operacional sem pressupor simultaneidade.
- Aceite: reserva/ocupação concorrente não duplica leito; higienização pendente impede disponibilidade indevida; cancelamento/correção conserva movimentos e Encounter coerentes.

### H14 — Completar a fase pré-analítica do laboratório

Dep: H04. Gate: G07.

- Evoluir pedidos/coletas para etiquetas, identificação de amostras, múltiplos materiais, recebimento, rejeição, recoleta, cancelamento e correção.
- Definir rastreabilidade pedido → amostra → transporte/recebimento e estados autorizados; evitar reaproveitamento indevido de accession_code.
- Preservar snapshots e registros v1; leitura de etiqueta só confirma etapa definida no contrato.
- Aceite: amostra errada, repetida ou rejeitada não avança silenciosamente; correções e recoletas preservam vínculo e motivo.

### H15 — Implementar resultados, validação e integração LIS

Dep: H14/H27 no trecho externo; H06 para assinatura aplicável. Gate: G07.

- Resultado estruturado com analito, valor/tipo, unidade, referência aplicável, origem, método quando exigido e versões.
- Fluxo de recebido, validado, liberado, retificado; registrar responsáveis e ciência de resultado crítico conforme política.
- Reutilizar a caixa em quarentena; parsing HL7/ASTM/arquivo deve validar origem, correlação e schema antes da incorporação clínica.
- Aceite: mensagem duplicada não duplica resultado; unidade/paciente/amostra incompatíveis ficam em revisão; retificação preserva original; arquivo recebido não é laudo liberado.

### H16 — Completar RIS e integrar PACS

Dep: H04/H27; H06 para laudos assinados. Gate: G07.

- Acrescentar agenda, preparo/prioridade quando aprovados, execução, estudo DICOM, laudo e retificação.
- Preferir integrar PACS/viewer aberto existente; avaliar Orthanc/OHIF. Definir armazenamento, recuperação e identificação patient/order/study.
- Proteger serviço DICOM/DICOMweb e acesso às imagens por escopo; um endereço difícil de adivinhar não é autorização.
- Aceite: pedido, estudo e laudo são correlacionados sem troca de paciente; usuário fora do escopo não acessa imagem; indisponibilidade/reenvio não cria estudo associado incorretamente.

### H17 — Implementar mapa cirúrgico e recursos

Dep: H04/H26. Gate: G08.

- Evoluir SurgicalCase para solicitação, análise, autorização pertinente, agendamento, remarcação e cancelamento.
- Reservar sala, equipe, duração e recursos com controle de conflitos e prioridade governada.
- Integrar avaliações pré-operatórias, preparo, documentos e consentimentos, distinguindo disponibilidade de autorização clínica.
- Aceite: concorrência não sobrepõe recurso exclusivo; cancelamento libera reservas de forma consistente; pedidos históricos permanecem preservados.

### H18 — Completar execução perioperatória

Dep: H17; H06/H19/H21 nos trechos utilizados. Gate: G08.

- Registrar checklist aprovado, tempos, equipe efetiva, anestesia, procedimento realizado, intercorrências, recuperação e destino.
- Rastrear materiais/medicamentos, lotes e OPME quando aplicável; integrar CME, estoque e cobrança.
- Não calcular risco, plano anestésico ou conduta sem conteúdo aprovado.
- Aceite: execução difere de solicitação; documentação e consumo mantêm autoria/histórico; correção de consumo gera movimento compensatório e efeito financeiro reconciliável.

### H19 — Implementar almoxarifado e movimentações de materiais

Dep: H02. Gate: G09.

- Evoluir InventoryItem/Requisition: locais, saldos, lotes/validade quando pertinentes, entrada, saída, transferência, reserva, atendimento parcial, devolução e inventário.
- Definir unidades e precisão; manter compatibilidade dos inteiros v1. Conversões de embalagem exigem regra versionada.
- Ledger ou mecanismo equivalente deve permitir conciliar cada saldo; ajustes exigem motivo e capacidade.
- Aceite: disputa pelo último saldo não produz estoque negativo; requisição não equivale a entrega; movimentos e estornos preservam origem.

### H20 — Implementar compras e recebimento

Dep: H19. Gate: G09.

- Fornecedor, solicitação consolidada, aprovação por competência, cotação quando exigida, pedido e recebimento parcial/completo.
- Registrar divergência, devolução e cancelamento; anexar documentos protegidos e vincular a obrigação financeira.
- Recebimento confirmado deve gerar entrada uma única vez; não somar estoque ao emitir pedido.
- Aceite: reenvio/recebimento concorrente não duplica entrada; quantidade/preço divergentes seguem aprovação; segregação entre solicitar, aprovar e receber segue política.

### H21 — Conciliar farmácia, materiais e consumo assistencial

Dep: H08/H19. Gate: G09 e políticas clínicas pertinentes.

- Manter o estoque farmacêutico existente como fonte de verdade dos medicamentos; definir fronteira explícita com materiais.
- Vincular requisição, reserva, dispensação/entrega, consumo, devolução e perda ao local/encontro quando aplicável.
- Integrar kits e unidades somente com regras aprovadas; evitar dois cadastros/saldos para o mesmo movimento.
- Aceite: prescrição → lote → dispensação → administração e material → entrega → consumo possuem rastreabilidade; retries e devoluções conciliam saldos sem duplicar cobrança.

### H22 — Capturar produção na conta hospitalar

Dep: H04 e módulos produtores do escopo; H21 para consumo. Gate: G09.

- Evoluir contas/itens existentes para registrar origem clínica/operacional, pagador, data, quantidade, unidade e regra de preço versionada.
- Capturar produção confirmada no momento aprovado; pedido de exame/cirurgia não prova execução nem autoriza cobrança.
- Implementar conciliação de eventos perdidos, duplicados e corrigidos; manter itens manuais com capacidade e justificativa.
- Aceite: cada origem fatura uma vez; preço histórico não muda com tabela nova; estorno preserva vínculo; totais exatos conciliam produção e consumo.

### H23 — Completar contratos, fechamento e cobrança

Dep: H22. Gate: G09.

- Pagador/convênio, plano, vínculo de cobertura, contrato, vigência, tabelas, pacote, diária, honorário e autorização conforme escopo.
- Fluxo de preparação, conferência, fechamento, emissão/envio, retorno, glosa, recurso, recebimento e estorno.
- Prever correção de lançamento sem edição destrutiva; suportar valores/quantidades necessários com Decimal e regras explícitas.
- Aceite: contrato fora da vigência não precifica silenciosamente; fechamento exige consistência; ajustes não apagam cobrança anterior; pagamento parcial e glosa são reconciliáveis.

### H24 — Implementar trilhas TISS/TUSS e SUS aplicáveis

Dep: H23/H27. Gates: G01/G09/G11.

- Confirmar versões vigentes e contratos nos portais oficiais ao implementar; registrar versão/schema em cada lote.
- Convênios: guias, autorizações, XML/esquemas, lotes, protocolos, demonstrativos, glosas e recursos exigidos.
- SUS: cadastros/identificadores, SIGTAP por competência e instrumentos pertinentes, como AIH, BPA e APAC; validar regras com o gestor.
- Aceite: geração valida contra schemas/regras aplicáveis; envio/retorno idempotente preserva protocolo; mock valida desenvolvimento, enquanto homologação exige parceiro/ambiente real autorizado.

### H25 — Completar financeiro ou integração com ERP

Dep: H20/H23. Gate: G09.

- Escolher pelo escopo implementação nativa ou integração com ERP, registrando quem é fonte de verdade.
- Contas a receber/pagar, baixa parcial, conciliação, estorno, caixa/banco, centros de custo e documento fiscal quando aplicável.
- Integrar obrigações de compra e receita hospitalar; não presumir serviço externo contratado.
- Aceite: cobrança, glosa, pagamento e devolução conciliam sem diferença monetária inexplicada; importação duplicada não duplica baixa; integração indisponível fica pendente recuperável.

### H26 — Completar credenciais, vínculos e escalas profissionais

Dep: H02. Gates: G01/G06 para regras assistenciais.

- Ampliar Employee sem confundir active cadastral com autenticação: registro profissional/UF, especialidade, vínculo, unidade e validade conforme política.
- Escala, disponibilidade, afastamento, troca de plantão, cobertura e conflitos; reutilizar recursos de agenda de H11/H17.
- Ponto e folha somente se incluídos; integrar sistema existente quando essa for a decisão.
- Aceite: vencimento/afastamento tem o efeito aprovado, sem apagar atos históricos; mesmo recurso não recebe disponibilidade incompatível em calendários separados.

### H27 — Completar interoperabilidade e processamento recuperável

Dep: H02/H03/H04. Gate: G11.

- Ampliar contratos FHIR conforme necessidades concretas: Patient, Encounter, Condition, AllergyIntolerance, Observation, pedidos, resultados e medicamentos aplicáveis.
- Validar perfis/terminologias; integrar RNDS somente aos modelos, credenciais e procedimentos aprovados.
- Criar o menor mecanismo persistente para importação/exportação: correlação, status, deduplicação, retries limitados, quarentena e reprocessamento autorizado. Reutilizar inbox/recibos existentes.
- Aceite: corrupção, mensagem fora de ordem, timeout, resposta perdida e reinício não geram sucesso fictício/duplicação; exportar Patient mínimo não é exportar prontuário completo. Sem nova API pública.

### H28 — Completar privacidade e governança documental

Dep: H02/H03; H06 quando envolver assinados. Gate: G10.

- Evoluir o acompanhamento de solicitações do titular para procedimento verificável de identidade, análise, atendimento, resposta e evidências.
- Definir minimização, retenção por classe, restrição, exportação e descarte permitido, preservando obrigações de guarda e impedimentos legais.
- Implementar revisão de acesso, acesso emergencial quando aprovado, trilha auditável, gestão de incidentes e responsabilidades de fornecedores.
- Aceite: fechar protocolo não significa automaticamente atender/excluir; retenção não apaga prontuário indevidamente; backup, logs, arquivos e dados locais entram no inventário. Não declarar conformidade jurídica por existência de uma tela.

### H29 — Permitir instalação independente de provedor de arquivos

Dep: H00.

- Preservar criptografia por versão, integridade e autorização. Tornar armazenamento configurável para opção autogerida adequada ao projeto, como filesystem privado ou S3 compatível.
- Remover exigência global de Pinata quando outro backend estiver selecionado; manter compatibilidade com CIDs e arquivos legados.
- Migrar com conferência de bytes/hash e disponibilidade antes de desativar origem; tratar versões legadas não cifradas por procedimento explícito.
- Aceite: instalação limpa funciona sem conta Pinata; download protegido verifica integridade; migração não perde versão/chave nem expõe arquivo por URL pública.

### H30 — Completar operação, backup e recuperação

Dep: H29 no trecho de armazenamento. Gate: G11.

- Automatizar backup cifrado do banco, arquivos, configuração necessária e chaves, com privilégios e guarda separados.
- Definir frequência, retenção, perda máxima aceitável e tempo de recuperação; testar restauração completa em ambiente isolado.
- Preparar atualização, migração única, rollback de código compatível, readiness, alertas, contingência, expiração de certificados e rotação segura de segredos.
- Implementar reempacotamento de chaves se necessário; nunca substituir FILE_ENCRYPTION_KEY diretamente.
- Aceite: restaurar também permite decifrar/abrir arquivos e reconciliar operações; demonstrar falha de dependência/reinício; registrar medição de recuperação e lacunas reais.

### H31 — Entregar indicadores e validar capacidade

Dep: módulos produtores correspondentes.

- Indicadores do escopo: ocupação/giro/permanência, espera, produção, pendências/tempos de exames, medicação, perdas/validade, receita/glosa e consumo.
- Formalizar numerador, denominador, janela temporal, fuso e fonte; proteger drill-down e exportações.
- Usar agregações/paginação; medir dados/concorrência representativos e otimizar gargalos observados.
- Aceite: indicador concilia com registros de origem e correções; filtros não vazam pacientes; registrar metas operacionais definidas e medição, sem promessa de capacidade não testada.

### H32 — Portal do paciente e teleatendimento, se incluídos

Dep: H02/H06/H11/H15 nos trechos usados. Gates: G01/G05/G10/G11.

- Portal com vínculo de identidade verificado, representantes autorizados, agendamento e acesso apenas a documentos/resultados liberados.
- Teleatendimento requer jornada real, consentimentos pertinentes, identificação, documentação, canal aprovado e contingência.
- Não reutilizar papel CLI como acesso automático ao PEP; tipo Encounter.TELEHEALTH não implementa teleconsulta.
- Aceite: paciente/representante só acessa o escopo permitido; liberação e revogação funcionam; diagnóstico/documento não liberado permanece protegido.

### H33 — Completar serviços especializados do escopo

Dep: núcleos clínico, estoque e faturamento pertinentes. Gates: G01 e responsável do serviço.

Tratar cada linha incluída como subcartão H33.x com contrato, implementação e DoD próprios. Não marcar este cartão DONE por criar menus ou um cadastro genérico.

| Subcartão | Entrega mínima, se aplicável |
| --- | --- |
| H33.1 — UTI | Plano assistencial, monitorização/balanços, dispositivos, escalas/protocolos aprovados, passagem de plantão e transferências. |
| H33.2 — Obstetrícia/neonatologia | Episódio gestacional/parto, vínculo mãe–recém-nascido, documentação e identificação própria, sem misturar prontuários. |
| H33.3 — Hemoterapia | Solicitação, amostra, compatibilidade validada, reserva, unidade/bolsa, administração, reação e hemovigilância com rastreabilidade. |
| H33.4 — CME | Materiais/conjuntos, recebimento, processamento, ciclo/lote, liberação e rastreamento até paciente/procedimento. |
| H33.5 — Infecção e segurança | Vigilância, eventos, investigação, isolamento e indicadores com definições/protocolos aprovados. |
| H33.6 — Nutrição e reabilitação | Avaliação, prescrição/plano, restrições, execução/entrega e evolução por profissional. |
| H33.7 — Engenharia clínica | Equipamento, localização, manutenção/calibração, indisponibilidade e impacto em agenda/recursos. |
| H33.8 — Outros serviços | Anatomopatologia, oncologia, diálise ou outros somente com escopo próprio aprovado e integração ao PEP. |

Aceite de cada subcartão: jornada completa testada com erro, correção, autorização e rastreabilidade; conteúdo clínico aprovado. Não automatizar decisão transfusional, anestésica ou terapêutica sem contrato e validação específicos.

### H34 — Consolidar distribuição aberta e instalação reproduzível

Dep: H29/H30.

- Preservar AGPL-3.0-only e créditos; conferir compatibilidade/licenças de código, imagens, catálogos e bases clínicas distribuídos.
- Instalação limpa, configuração mínima, validação de segredos, migração, atualização e desinstalação com preservação/exportação dos dados.
- Dados demonstrativos estritamente sintéticos, comando explícito e proteção contra execução acidental em ambiente real.
- Versionar release/notas de migração e guias curtos por perfil; documentar dependências opcionais e indisponibilidades.
- Aceite: instalar em ambiente limpo, atualizar uma base anterior e restaurar backup com procedimentos documentados; nenhuma credencial pública de teste ou base clínica não licenciada na distribuição.

### H35 — Homologar o produto e encerrar o plano

Dep: todos os cartões obrigatórios e subcartões incluídos.

- Executar a matriz de jornadas da seção 08, verificações da seção 07, atualização/legados e recuperação.
- Realizar homologação com responsáveis e integrações reais autorizadas. Manter evidências/versionamento; corrigir regressões.
- Avaliar privacidade, acessos, concorrência, integridade, desempenho e operação dos fluxos completos.
- Aceite: todos os itens aplicáveis DONE, N/A justificados, decisões aprovadas, regressões resolvidas e procedimentos executáveis. READY/BLOCKED obrigatório impede declarar implantação concluída.
- Entregar release revisável e lista objetiva de limitações remanescentes. Publicação depende da autorização existente.

## 07 — Verificação proporcional e comandos

Antes de executar, confirmar os comandos no checkout atual. A base usa Python >=3.14, uv, Django e testes existentes. Não adicionar pytest, DRF, Celery ou framework frontend apenas para cumprir o plano.

Durante cada cartão: testes da regra e da superfície afetadas; adicionar regressão para risco real. PostgreSQL é necessário para provar concorrência/bloqueios usados pelo domínio. SQLite não substitui essa evidência.

~~~bash
uv sync --frozen --dev
uv run python manage.py check
uv run python manage.py test apps.clinical.pep --verbosity 1
# Substitua o módulo pelo afetado; inclua consumidores quando houver mudança de contrato.
uv run python manage.py makemigrations --check --dry-run
~~~

Em marcos integrados e na entrega final, executar os gates existentes aplicáveis:

~~~bash
uv run ruff check aegis_share apps mysite
uv run ruff format --check aegis_share apps mysite
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test --verbosity 1
uv run python manage.py collectstatic --noinput
~~~

Rodar Playwright/axe, validação Compose, jornadas e privacidade seguindo .github/workflows/django.yml e configurações atuais. Usar ambiente descartável. Scripts prepare_* e senhas E2E são exclusivos de teste; não executá-los em produção.

Sem infraestrutura/credenciais necessárias, registrar comando, impedimento e teste substituto realizado. Não escrever “aprovado” para teste não executado. Não executar migrate em banco real como parte de teste.

Em alteração de schema, verificar migração com dados legados representativos em cópia autorizada/sanitizada. Em integração externa, testar contrato/mocks e separar evidência de homologação real.

## 08 — Matriz final de jornadas e falhas

| Jornada | Evidência exigida |
| --- | --- |
| Ambulatório | Agendar → identificar/chegar → atender → registrar/assinar → solicitar diagnóstico → resultado liberado → concluir/retornar. |
| Urgência, se incluída | Chegada → classificação/reavaliação → atendimento → observação, internação, transferência ou alta; tempos e prioridades preservados. |
| Internação | Admitir → ocupar leito → cuidados/medicação → transferir → alta clínica/documentos → preparação/liberação do leito. |
| Medicação | Prescrever → revisar → validar → dispensar por lote → administrar ou registrar exceção → reconciliar/devolver quando necessário. |
| Laboratório | Pedido → identificação/coleta → recebimento/rejeição → resultado → validação/liberação → retificação/ciência quando exigida. |
| Imagem | Pedido → agenda → execução → estudo correto → laudo assinado/liberado → acesso autorizado. |
| Cirurgia | Solicitar → avaliar/consentir → reservar → executar/checklist → consumo → recuperação → PEP e conta conciliados. |
| Suprimentos | Requisitar → aprovar/comprar → receber → movimentar → entregar/consumir → devolver/ajustar → conciliar saldo. |
| Receita | Produção → regra contratual → conta → conferência/fechamento → envio → retorno/glosa → recurso/baixa → conciliação. |
| Titular e acesso | Verificar identidade → registrar/analisar → atender conforme política → comprovar resposta; revogação protege acessos posteriores. |
| Distribuição | Instalar sem Pinata quando configurado → atualizar com legados → restaurar banco/arquivos/chaves → retomar operação. |

Falhas obrigatórias, quando pertinentes:

- Dois operadores disputam último leito, horário, lote ou saldo.
- Resposta HTTP se perde após commit; retry não duplica o ato.
- Processo cai entre persistência e envio externo; reinício reconcilia.
- Mensagem externa é duplicada, atrasada, malformada ou de paciente/origem incompatíveis.
- Permissão/vínculo é revogado com formulário aberto.
- Encontro encerra entre leitura e gravação.
- Conteúdo assinado ou resultado liberado precisa de correção.
- Estoque/conta recebe devolução, estorno ou recebimento parcial.
- Rede cai durante medicação/dispensação; a interface não confirma sucesso inexistente.
- Backup é restaurado, com arquivos decifráveis, estados consistentes e operações pendentes identificadas.
- Dados sensíveis não aparecem em logs, push, cache indevido ou acesso cruzado.

Registrar resultado por jornada, commit e evidência. Não duplicar dezenas de testes que verificam a mesma regra no mesmo nível.

## 09 — Fontes de consulta e atualização

Código e contratos do checkout são a referência técnica inicial. Para requisitos externos, consultar apenas a parte oficial necessária ao cartão e registrar versão/data. Não fixar este documento como prova de legislação ou de schema vigente.

- Repositório: https://github.com/ArcoverdePedro/AegisShare
- Baseline: https://github.com/ArcoverdePedro/AegisShare/commit/38c6100d54d9bbf45e18e4e8af1bdf73b13954e5
- RNDS: https://fhir.saude.gov.br/ e https://rnds-fhir.saude.gov.br/
- TISS/ANS: https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss/
- DATASUS/SIA: https://sia.datasus.gov.br/
- LGPD: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
- SBIS — requisitos S-RES: https://sbis.org.br/certificacoes/certificacao-software/manuais-e-listas-de-requisitos/
- Orthanc/OHIF: https://orthanc.uclouvain.be/book/plugins/ohif.html

## 10 — Prompt curto para iniciar ou retomar

~~~text
Implemente o AEGISSHARE_PLANO_EXECUCAO_IA.md neste repositório.
Siga o núcleo 00–05 e os AGENTS.md aplicáveis. Confira o checkout real.
Leia apenas o cartão ativo e as referências necessárias; mantenha checkpoint.
Reutilize o existente, entregue fluxos completos e avance nas tarefas elegíveis.
Preserve gates clínicos/jurídicos e a arquitetura sem nova API REST pública.
Não declare mocks como homologação. Não pare após planejar ou concluir um cartão.
Economize tokens em leituras, logs e respostas, preservando validação e segurança.
~~~

