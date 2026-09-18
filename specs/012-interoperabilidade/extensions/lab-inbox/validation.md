# Evidências locais — 2026-09-18

Aprovação explícita: mensagem do usuário “[@Ponytail] aprovado, continue”, em continuidade à proposta desta extensão. Implementação concluída para piloto sintético; aprovação institucional para uso real permanece separada.

| Verificação | Resultado |
|---|---|
| Suíte completa Django / PostgreSQL 18 | 450 testes, todos passaram; inclui locks/concorrência |
| Interoperabilidade após ajuste final dos headers ASGI e piso do spool | 35 testes passaram no PostgreSQL após os ajustes finais; teste ASGI também passou após resolver a rota por nome |
| Ruff check / format | Passaram nos arquivos Python da extensão e configuração alterada |
| Django check / makemigrations --check --dry-run | Sem problemas / sem alterações |
| Migration em SQLite descartável | Aplicar 0002, reverter para 0001 e reaplicar: OK |
| Playwright Chromium, sem retries | 3 jornadas passaram |
| Axe WCAG em 390×844 e 768×1024 | Lista/form/detalhe sem violações sérias/críticas e sem overflow horizontal |
| Offline | Sem confirmação, filas/contagens IndexedDB inalteradas; nenhuma página da caixa ou marcador do arquivo no Cache Storage/localStorage/sessionStorage |
| agent-browser | Tela de recebimento renderizada, campos esperados, sem erros reportados |
| Logs sintéticos | Marcador do payload e filename original ausentes dos logs de servidor e testes PostgreSQL |
| Bandit / pip-audit | Sem findings no app (testes excluídos) / sem vulnerabilidades conhecidas nas dependências instaladas |
| Lighthouse, URL raiz pública local | Acessibilidade 0,98; boas práticas 1,00; SEO 0,90; desempenho 0,73, aviso abaixo de 0,90. Gates de erro passaram |

Não foi executado CI remoto nem deployment. Lighthouse público não mede a jornada autenticada; esta foi verificada via Playwright/axe. Dados, banco, chaves e contas dos testes são sintéticos.

## Rastreabilidade executável

- **CA-INBOX-01:** `tests/test_lab_inbox.py`: autorização interna/capacidades, associação e confirmação; `tests/e2e/lab_inbox_journeys.spec.js`: recebimento e recibo. Fixture em `tests/e2e/prepare_lab_inbox.py`, adicionada ao CI existente.
- **CA-INBOX-02:** testes HTTP de revogação, origem inativa, histórico e capacidade sem associação; E2E de outro operador com mesmas capacidades e sem origem.
- **CA-INBOX-03:** vazio, incompleto, arquivo acima/exatamente no limite, múltiplos arquivos, corpo excessivo e leitura sem tamanho confiável; mock de TemporaryUploadedFile impede spill; `tests/test_asgi.py` rejeita antes de entregar chunk excessivo ao Django.
- **CA-INBOX-04:** decifração exata em teste com AAD do UUID, AAD incorreta e ciphertext adulterado rejeitados; erro de chave/criptografia e rollback. Nenhuma rota decifra conteúdo.
- **CA-INBOX-05:** reenvio preserva recibo/autoria, outra origem gera outro; `tests/test_concurrency.py` executa recebimentos simultâneos reais no PostgreSQL e confirma um recibo.
- **CA-INBOX-06:** imutabilidade, ACCESS, falha de auditoria reverte criação; HTML/auditlog sem payload, hashes, chaves e filename; SQL de metadados exclui blobs; paginação audita apenas os 25 renderizados; associações auditadas.
- **CA-INBOX-07:** CSRF/métodos/erros com no-store; E2E offline e mobile/axe; gates acima.

Os paths `tests/test_*.py` nesta lista são relativos a `apps/interoperability/`. Os cenários Gherkin documentam aceitação; os testes Django e Playwright são executáveis.
