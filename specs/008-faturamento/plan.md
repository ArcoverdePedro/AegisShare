# Plano — preparação manual de contas

Plano executado após autorização em 2026-09-18. Nível 1/2/3. [Evidências](validation.md).

1. App billing, duas tabelas, capacidades/constraints/checks/migration reversível; auditlog exclui descrições/valores. Sem Admin financeiro.
2. Forms/confirmações e funções específicas de abertura/lançamento com revalidação PEP/locks/retries; não copiar exigência OPEN das mutações clínicas.
3. Quatro FBVs/templates, navegação/namespace privado, paginação e aggregate ORM Decimal exato; sem coleção completa ou float.
4. Testar limites/valores não finitos/casas excessivas/fração, zero válido, conta vazia, 0.10 × 3 + 0.20 = 0.50, preço/quantidade máximos e total além da primeira página.
5. Testar confirmação/autoria, conta única, equivalência Decimal/trim, conflitos, chave nova distinta, revogação/inativo e preparação após encerramento. PostgreSQL: retries, aberturas com chaves diferentes e colisões entre agregados; rollback de auditoria.
6. Migration aplicar/reverter/reaplicar em banco descartável. HTTP/queries sem N+1; E2E de conta/item/retry/total, revogação Admin, mobile/axe e offline.
7. Ruff/Django/migrations/suíte/PostgreSQL/Bandit/pip-audit/Lighthouse. Avisos explícitos; sem testes reais de cobrança ou meta de desempenho presumida.
8. Guia de limites/separador monetário, retirada preservando dados e rastreabilidade real. Sem CI remoto/deployment/validação institucional declarados sem evidência.

SQLite usa um agregado nativo de centavos inteiros para evitar perda de precisão e overflow do SUM; PostgreSQL usa SUM numérico tipado. Ambos foram testados com os valores máximos.
