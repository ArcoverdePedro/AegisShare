# Plano — catálogo e requisições

Plano executado após autorização do recorte em 2026-09-18; [evidências](validation.md). Nível 1/2/3.

1. App inventory, InventoryItem/Requisition, permissões, constraints/check e migration reversível; auditlog sem textos/quantidade. Admin nativo apenas do catálogo.
2. Form nativo e função específica validando entrada, capacidades, catálogo/lock, snapshots, confirmação e retries. Não generalizar serviços de cirurgia/faturamento que têm regras distintas.
3. Quatro FBVs/DTL, menu, middleware privado, paginação/related queries e auditoria de leituras, inclusive seleção renderizada do formulário.
4. Testar quantidades/UUID/confirmação, catálogo inativo, snapshots após edição, retry após desativação, revogação de permissão, consulta institucional e cliente/ADM sem capacidade.
5. PostgreSQL real: retry concorrente mesmo item, mesma chave em itens diferentes e conflito entre atores/conteúdos. Nova chave distinta. Falha de auditoria/integridade não identificada reverte e não confirma sucesso.
6. Testar listas >25, ACCESS por página, detalhe sem N+1, Admin/PROTECT/append-only e HTTP/CSRF/headers/erros. Migration aplicar/reverter/reaplicar em banco descartável.
7. E2E criar/retry/snapshot/revogação efetiva de capacidade com form aberto; mobile/tablet/axe e offline sem cache/fila. Fixture sintética no CI existente.
8. Ruff/check/migrations/suíte/PostgreSQL/Bandit/pip-audit/Lighthouse e links. Guia/evidências: URL medida, avisos, limites e testes executados, sem afirmar CI remoto/deployment/produção.

Sem eventos sem consumidor, classes de serviço, biblioteca nova ou mudança nos modelos farmacêuticos.
