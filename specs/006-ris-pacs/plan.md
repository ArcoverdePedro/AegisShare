# Plano — RIS v1

Status: aprovada e implementada em 2026-09-18; [evidências](validation.md). Nível 1/2/3 — reuso, Django nativo e FBVs.

1. Criar app ris, os dois modelos, permissões e Admin exclusivo do catálogo; migration reversível e exclusões de auditlog. Sem catálogo clínico pré-carregado.
2. Form Django e função específica de mutação: transação/locks, revalidação PEP, snapshot, UUID de operação e retry. Extração justificada por concorrência testada diretamente e legibilidade da FBV; sem classe de serviço/base genérica.
3. Três FBVs, URLs nomeadas e templates, com paginação antes de auditoria e queries relacionadas. Reusar layout/partial de campos existente e link pelo encontro. Sem JS novo.
4. Estender middleware privado e navegação para /imagem/; confirmar network-only da PWA sem fila. Não publicar evento, pois não existe consumidor RIS neste recorte.
5. Testar capacidades/escopo, fechamento, catálogo desativado, snapshots, chave incompatível, falha de auditoria, concorrência PostgreSQL e ausência de dados clínicos em logs. Aplicar/reverter/reaplicar migration em banco descartável.
6. E2E com fixture sintética: criação/retry, outro operador, revogação após abrir formulário, telefone/tablet com axe e offline sem persistência. Reusar runner existente.
7. Ruff, Django check, migrations, suíte adequada e PostgreSQL, Bandit/pip-audit, gates Lighthouse existentes. Registrar avisos/limites; Lighthouse da página pública não substitui axe da jornada autenticada.
8. Guia operacional e rastreabilidade para nomes reais dos testes. Não marcar execução remota, implantação ou validação institucional sem evidência.

O piso da v1 termina no pedido “Solicitado”. Extensões PACS/laudos necessitam contratos reais e aprovação própria; não antecipar tabelas, dependências, infraestrutura ou enums para elas.
