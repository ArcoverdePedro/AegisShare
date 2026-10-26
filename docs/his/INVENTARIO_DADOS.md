# Inventário técnico de dados pessoais

Levantado do código em 26/10/2026 (H28). Descreve onde os dados ficam e como saem; não define base legal, retenção nem conformidade — isso é G10.

| Local | Conteúdo | Proteção existente | Sai por |
| --- | --- | --- | --- |
| PostgreSQL — PEP (`pep_*`) | identificação, nome social, contatos, endereço, encontros, evoluções, concessões de acesso | escopo por `accessible_patients`; auditlog com campos sensíveis excluídos/mascarados | telas, exportação FHIR mínima, backup |
| PostgreSQL — ADT, RX, enfermagem, LIS, RIS, cirurgia, agenda | atos clínicos e operacionais ligados ao `Encounter` | capacidades + escopo PEP/unidade; histórico append-only | telas, backup |
| PostgreSQL — faturamento, estoque, RH | conta por encontro, itens; materiais; cadastro funcional, registro profissional, ausências (sem motivo de saúde) | capacidades; estornos em vez de exclusão | telas, backup |
| PostgreSQL — LGPD (`compliance_*`) | solicitações do titular, notas | capacidade + escopo PEP; notas fora do auditlog | telas, backup |
| PostgreSQL — `auditlog_logentry` | ator, objeto, ação, campos não excluídos | só administradores (`/auditoria/`) | backup |
| PostgreSQL — caixa laboratorial | bytes recebidos cifrados (AES-GCM, chave embrulhada) | sem download/preview | backup |
| `FILE_STORAGE_ROOT` ou Pinata | arquivos cifrados por versão | AES-256-GCM, hash verificado no download; diretório 0700 | download autorizado, backup (`files-*.aegisbak`); CIDs na Pinata ficam no provedor externo |
| Backups (`scripts/backup.sh`) | dump completo + arquivos | cifrados com `BACKUP_ENCRYPTION_KEY` | onde o operador guardar |
| Redis / cache | sessões e cache de health | sem dado clínico intencional | — |
| Logs JSON (stdout) | requisições, eventos técnicos | sem PHI textual nos eventos ADT/PEP; teste E2E procura valor clínico sintético nos logs | coletor de logs do operador |
| Sentry (se `SENTRY_DSN`) | erros | `send_default_pii=False` | fornecedor externo |
| Navegador — IndexedDB `offline_queue.js` | sinais vitais pendentes (único fluxo offline) | cifrado no cliente (WebCrypto) e limpo após envio/logout | sincronização |
| Navegador — Web Push | assinatura do dispositivo | payload minimizado | provedor de push |

Revisão de acesso: `python manage.py access_review > revisao.csv` lista, por usuário, pacientes concedidos (só UUID), unidades ADT, arquivos compartilhados, permissões diretas/por grupo e superusuários. Não altera nada; revogar segue pelo Admin.

Pendentes (G10): retenção por classe, descarte permitido, acesso emergencial, gestão de incidentes, contratos com fornecedores (Pinata, Sentry, push), verificação de identidade e resposta formal ao titular.
