# Plano — solicitações cirúrgicas v1

Status: autorizado em 2026-09-18 e implementado; [evidências](validation.md). Nível 1/2/3.

1. App surgery, dois modelos, capacidades, Admin apenas do catálogo e migration reversível. Sem catálogo clínico pré-carregado.
2. Form e função específica de registro: locks, revalidação PEP/OPEN, retrato, retry e constraint; funções existentes PEP compartilhadas, sem base genérica de solicitações.
3. Três FBVs/templates, paginação antes de ACCESS, queries relacionadas, entrada pelo encontro e menu. Layout/partial existente; sem JS novo.
4. Namespace privado e fronteira PWA network-only; sem fila ou evento sem consumidor.
5. Testar capacidade/escopo, fechamento/revogação com formulário aberto, snapshots, catálogo inativo/retry, conflito sem revelar registro, auditlog minimizado e rollback de criação/leitura. Concorrência real no PostgreSQL, incluindo colisão entre encontros.
6. Aplicar/reverter/reaplicar migration em banco descartável. E2E sintético com criação/retry, outro operador e revogação pelo Admin; telefone/tablet/axe e offline sem persistência.
7. Ruff, Django check, migrations, suíte apropriada/PostgreSQL, Bandit/pip-audit e gates Lighthouse existentes. Registrar avisos, incluindo dívida de desempenho já observada no Core, sem equiparar aviso a meta atingida.
8. Guia operacional, retirada preservando dados e rastreabilidade para nomes reais de testes. Sem afirmar CI remoto/deployment ou validação institucional sem evidência.
