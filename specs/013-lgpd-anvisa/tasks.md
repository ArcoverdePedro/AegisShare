# Tarefas — Spec 013 v1

Status: v1 aprovada pelo mantenedor em 2026-09-16; implementação e validação local concluídas; evidências e limites em `validation.md`. Tarefas dimensionadas para até um dia; dividir se necessário. Marcação concluída significa somente trabalho efetivamente realizado.

- [x] **T-LGP-01:** inventariar fronteiras do Core/PEP/Interop e preparar spec, plano, modelo e contratos (CA-LGP-01–07).
- [x] **T-LGP-02:** aprovação explícita recebida do mantenedor: “aprovado, continue”.
- [x] **T-LGP-03:** criar app/models/permissões/migration e validar rollback em banco descartável (CA-LGP-01/02).
- [x] **T-LGP-04:** implementar forms e FBVs de criação/lista/detalhe, com RBAC+ABAC, paginação e testes HTTP (CA-LGP-01/03/07).
- [x] **T-LGP-05:** implementar transições atômicas, lock e conflito 409; testar dupla submissão no PostgreSQL (CA-LGP-02/04).
- [x] **T-LGP-06:** integrar auditoria minimizada de acesso/mutação e testar rollback sob falha (CA-LGP-05/07).
- [x] **T-LGP-07:** integrar cabeçalhos de privacidade e testar fronteira network-only/cache/fila (CA-LGP-06).
- [x] **T-LGP-08:** conectar cenários aos testes Django/Playwright; testar fluxo completo, telefone/tablet e axe (CA-LGP-01–07).
- [x] **T-LGP-09:** executar gates de lint, Django, migrations, segurança, PWA e concorrência, registrando limites de ambiente (todos os critérios).
- [x] **T-LGP-10:** publicar guia operacional e matriz de rastreabilidade real, sem alegação de certificação jurídica (todos os critérios).

## Gates externos e extensões futuras

- Procedimento institucional de recebimento, identidade/representação, escopo e atendimento antes de usar dados reais.
- Definição de bases legais, consentimentos, retenção, backups e decisões sobre pedidos antes de automatizar efeitos sobre dados.
- Avaliação de risco/enquadramento regulatório e certificações sob escopo próprio.
- Extensão de ingestão HL7/ASTM da Spec 012 antes do LIS; os gates clínicos das demais specs continuam vigentes.
