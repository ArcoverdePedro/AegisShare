# Progresso do plano HIS

Base: 38c6100 (master, 26/10/2026) | Escopo: G01 pendente — provisório sintético em `DECISOES.md`

Mapa de capacidades na base (fluxo real, não nome de app): PEP com Patient/Encounter/evolução+adendo/grants; ADT com leitos e movimentos; RX com prescrição, revisão determinística, lotes e dispensação; enfermagem com sinais vitais e administração confirmada; LIS/RIS/cirurgia só pedido/coleta/solicitação; billing com conta manual; inventory com item e requisição (inteiros, sem ledger); HR cadastro; FHIR mínimo + caixa laboratorial; LGPD com protocolo do titular; arquivos cifrados só na Pinata (até H29). Ausentes: alergias, assinatura, agenda/recepção, triagem, resultados LIS, compras, contratos/TISS/SUS, financeiro, backup automatizado, indicadores.

| ID | Estado | Evidência/commit | Bloqueio ou próxima ação |
| --- | --- | --- | --- |
| H00 | DONE | baseline: check, makemigrations --check, ruff check OK; 525 testes OK em PostgreSQL 18 descartável | Preexistente: `ruff format --check` acusa 74 arquivos com ruff 0.17 (não é gate do CI) |
| H01 | BLOCKED | `docs/his/DECISOES.md` | G01 sem resposta; escopo provisório registrado, trabalho técnico segue |
| H29 | READY | branch `his/plano-execucao`; `aegis_share/tests/test_file_storage.py` | Falta instalação real com volume e migração de acervo Pinata real (G11) |
| H19 | READY | `apps/admin/inventory/tests/test_stock.py`, `test_concurrency.py` (PostgreSQL) | Reserva, conversão de embalagem e ponto de pedido aguardam G09; falta homologação com almoxarifado real |
| H20 | READY | `apps/admin/inventory/tests/test_purchases.py`, `test_concurrency.py` | Cotação/alçadas/anexos/devolução ao fornecedor e vínculo financeiro aguardam G09/H25 |
| H03 | BLOCKED | `apps/clinical/pep/tests/test_registration.py`; spec 001 "Extensão de cadastro" | Parte técnica entregue; desconhecido/provisório, múltiplos identificadores, responsáveis e mesclagem dependem de G02 |
| H30 | READY | `aegis_share/tests/test_backup.py`; ensaio de restauração registrado no README | Agendamento, retenção, RPO/RTO, cópia externa, alertas e rotação/reempacotamento de chaves dependem de G11 |
| H11 | READY | `apps/clinical/scheduling/tests/`; `docs/agenda-ambulatorial.md` | Acesso do profissional ao paciente agendado (G02/H02), integração com escala (H26), canal externo e painel público pendentes |
| H27 | BLOCKED | caixa laboratorial já deduplica e mantém quarentena | Processador/retry sem formato de equipamento (G07) e RNDS sem credenciais (G11); FHIR ampliado depende de H04/H05 |
| H05, H06, H07 | BLOCKED | specs/001-pep extensão, T-PEP-08, T-RX-02, T-NUR-09 | G03, G05, G04 |
| demais | TODO | — | — |

Última verificação: `manage.py test --parallel 4` (PostgreSQL 18) → 564 OK; ruff check e makemigrations --check OK
Próxima tarefa: H13 — ler `apps/clinical/adt/` e acrescentar estado operacional do leito (higienização/bloqueio justificado) sem misturar com ocupação.
