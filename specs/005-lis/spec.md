# Spec 005 — LIS v1: pedidos e coleta de amostras

## Status

**Aprovada em 2026-09-17** pela instrução do mantenedor “aprovado, implemente”. Recorte v1 implementado; evidências em [validation.md](validation.md).

## Contexto e recorte

PEP, ADT, prescrição, enfermagem e os recortes 012/013 estão disponíveis. O próximo módulo do roadmap é o laboratório. A Spec 012 entrega exportação cadastral; ainda não entrega ingestão de resultados HL7/ASTM.

Esta v1 registra um pedido para um exame de catálogo institucional e uma coleta correspondente, sem produzir resultados ou se conectar a equipamentos. A dependência da extensão 012 permanece bloqueante para ingestão e liberação de resultados, mas não para este fluxo manual interno. Aprovar esta spec inclui aprovar esse sequenciamento explícito.

## User Stories

- Como profissional autorizado, quero solicitar um exame para um encontro aberto acessível no PEP, preservando exame, material, autor e horário.
- Como profissional de coleta autorizado, quero registrar uma coleta vinculada ao pedido, com identificação da amostra e horário, sem duplicar o registro ao reenviar o formulário.
- Como profissional autorizado, quero consultar o pedido e a coleta com histórico preservado e leitura auditada.

## Requisitos funcionais

- **RF-LIS-01:** catálogo institucional `LabTest` com código único, nome, material e indicador ativo. Manutenção pelo Django Admin e permissões nativas; sem cadastro paralelo de usuários ou pacientes. Sem exames clínicos pré-carregados.
- **RF-LIS-02:** pedido `ServiceRequest` vinculado a `Encounter` e a um exame ativo; um exame por pedido. Autor e horário definidos pelo servidor; retrato de código/nome/material preservado no pedido. Não há edição, cancelamento ou exclusão pela UI nesta v1.
- **RF-LIS-03:** uma `Specimen` por pedido, com código de amostra, horário de coleta informado e profissional autenticado. Código único no módulo, após remoção de espaços externos; comparação exata, sensível a maiúsculas. Material herdado do pedido, sem conversão ou inferência.
- **RF-LIS-04:** sessão, profissional interno, capacidade específica e `accessible_patients(user)` em cada GET/POST. Exigir encontro aberto na solicitação e na coleta; revalidar dentro da transação. Leitura de histórico permitida após fechamento se o paciente continuar acessível. Não criar concessões PEP.
- **RF-LIS-05:** lista paginada de 25 pedidos, detalhe e acesso pelo encontro. Situação derivada da presença de amostra: “Solicitado” ou “Coleta registrada”. Não manter coluna de estado redundante.
- **RF-LIS-06:** operação identificada por UUID oculto. Retry do mesmo ator com mesma chave e conteúdo normalizado retorna o registro original após revalidar autorização; chave com conteúdo diferente ou coleta já ocupada retorna 409. Uma nova chave representa um novo pedido; não deduplicar exames por nome/paciente.
- **RF-LIS-07:** auditar criação e leitura identificável com ator. Gravação e auditoria na mesma transação; falha reverte a mutação. Logs e auditlog genérico não copiam código de amostra, nome de exame, material, nome de paciente ou texto clínico.

## Requisitos não funcionais

- **RNF-LIS-01:** Django Forms/ModelForms, FBVs e templates existentes; sem nova dependência, SPA, fila ou worker.
- **RNF-LIS-02:** todas as respostas do namespace protegidas por `private, no-store`, `Vary: Cookie` e `nosniff`, inclusive redirects, CSRF e erros. Formulários escapam conteúdo; payload sensível protegido nos relatórios de erro.
- **RNF-LIS-03:** consultas relacionadas carregadas em lote, sem N+1 de leitura. Concorrência validada em PostgreSQL; constraint de unicidade é a proteção final para coleta/chaves/código.
- **RNF-LIS-04:** somente online, fora da fila IndexedDB, Cache Storage e push. Telefone/tablet sem overflow e axe sem violações sérias/críticas.
- **RNF-LIS-05:** semântica de coleta é registro informado pelo operador, sem afirmar conferência automática de identidade, qualidade/aceitação da amostra ou autorização para liberar laudo.

## Telas e fluxo

Encontro → solicitar exame → detalhe do pedido → registrar coleta → detalhe com amostra. Menu Laboratório → pedidos acessíveis → detalhe. Catálogo vazio apresenta orientação de configuração, sem criar exames fictícios automaticamente.

## Fora de escopo

Resultados, valores críticos, interpretação, laudos, assinatura, ingestão HL7/ASTM, analisadores, integração com faturamento, etiquetas/código de barras, painéis de múltiplos exames, múltiplas amostras, recoleta, cancelamento, correção, recebimento/aceitação/rejeição de material e prazos clínicos. A v1 é um piloto sintético até aprovação do catálogo e procedimento operacional; uso real que exija correções depende de extensão com histórico definido.

## Dependências e riscos

Specs 000/001/014 para sessão, escopo, auditoria e fronteira PWA. Extensão 012 necessária antes de resultados automatizados. Governança institucional deve definir exames, materiais, profissionais autorizados e identificação física da amostra; a implementação não inventa códigos ou protocolos clínicos.

O registro append-only na aplicação não protege contra administrador do banco. Um código digitado não comprova identidade física; a UI solicita confirmação pelo operador. Pacientes inativos continuam fora do escopo PEP. O fechamento concorrente do encontro deve ser serializado com a escrita LIS pelo lock da linha do encontro.

## Aceitação e rastreabilidade

Cenários em [features/orders-and-specimens.feature](features/orders-and-specimens.feature). Cobertura HTTP em `apps/clinical/lis/tests/test_workflow.py`, concorrência em `test_concurrency.py` e navegador em `tests/e2e/lis_journeys.spec.js`. Resultados registrados separadamente em validation.md.

| Requisitos | Rota/FBV | Template | Critério/cobertura |
|---|---|---|---|
| 01/02/04 | `order_create` | `lis/order_form.html` | CA-LIS-01/03; catálogo e escopo |
| 03/04 | `specimen_create` | `lis/specimen_form.html` | CA-LIS-02/03; horário, confirmação e unicidade |
| 05 | `order_list`, `order_detail` | lista/detalhe | CA-LIS-04; paginação, histórico e queries |
| 06 | POSTs | forms/detalhe | CA-LIS-05; retry e concorrência PostgreSQL |
| 07 | todas | HTML/erro seguro | CA-LIS-06; rollback e minimização |
| RNF-02/04 | todas + PWA | forms/offline | CA-LIS-07; CSRF, headers, Playwright/axe |

## Definition of Done

- [x] Spec, plano, modelo, contratos e cenários preparados.
- [x] Aprovação explícita do mantenedor.
- [x] Implementação, migration e rollback descartável.
- [x] Testes HTTP, autorização, auditoria, retry e concorrência.
- [x] Playwright, mobile/axe, privacidade PWA e gates locais com limitações registradas.
- [x] Guia operacional e rastreabilidade com testes reais.
- [ ] Avaliação institucional para uso real (gate externo, sem bloquear piloto sintético).
