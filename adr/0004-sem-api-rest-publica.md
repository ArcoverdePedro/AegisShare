# ADR-0004 — Sem API REST pública

## Status
Aceito em 2026-09-11 após aprovação explícita da arquitetura HIS.

## Contexto

O AegisShare atual possui rotas `api/v1/*` para arquivos. O HIS alvo é uma aplicação interna fullstack monolítica, com Django Templates + HTMX + Alpine.js, e define que integrações externas devem ocorrer por arquivos, mensageria ou jobs internos.

## Decisão

Não criar novas APIs REST públicas. Funcionalidades de interface usam views Django server-rendered, formulários, HTMX e WebSockets autenticados. Integrações usam arquivos, Celery/Redis e canais internos conforme contratos.

As rotas REST existentes serão tratadas como legado: primeiro inventariar consumidores, depois oferecer caminho de migração e somente então remover/desabilitar de forma controlada.

## Consequências

### Positivas
- reduz superfície pública de ataque;
- mantém um único modelo de autenticação/autorização para o produto interno;
- evita criar uma segunda camada de contratos HTTP para cada módulo clínico.

### Negativas
- consumidores atuais de `api/v1/*` precisarão de migração;
- algumas integrações exigirão jobs ou troca de arquivos em vez de chamadas REST.

### Neutras
- JSON técnico para health checks internos não é considerado API de negócio pública;
- respostas internas auxiliares a HTMX/fetch autenticado podem existir quando documentadas e não expostas como API pública reutilizável.
