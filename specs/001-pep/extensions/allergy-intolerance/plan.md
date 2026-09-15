# Plano Técnico — AllergyIntolerance estruturada

## Arquitetura

Extensão futura do app `apps.clinical.pep`, mantendo o monólito Django e integração Python interna com a Spec 003. Nenhuma API REST pública.

## Modelo de Dados

Adicionar `AllergyIntolerance` somente após validação clínica dos estados/terminologia definidos em `spec.md`. Histórico deve ser preservado e auditado.

## Rotas e Views

Nenhuma rota neste incremento documental. Antes da implementação, registrar as futuras FBVs em `specs/001-pep/contracts/routes.md`.

## Formulários e Validação

Nenhum formulário neste incremento. Antes da implementação, registrar contrato de formulário com choices governadas e validação de escopo PEP.

## Templates e HTMX

Futuro componente no detalhe do paciente, sempre `no-store`; HTMX apenas para interações autenticadas e server-rendered.

## Eventos Internos

Não publicar texto de alergia/reação em eventos. Qualquer evento futuro deve transportar apenas identificadores técnicos e estado mínimo necessário.

## PWA

Dados de alergia não entram no cache/offline por padrão. Qualquer exceção exige spec PWA clínica explícita e revisão LGPD.

## Segurança e LGPD

RBAC + ABAC PEP, auditoria de leitura/mutação, minimização de PHI e sem logs textuais sensíveis.

## Migrações

Pendente da aprovação clínica. Deve ser reversível e não remover histórico.

## Testes Futuros

- model/constraints;
- autorização PEP;
- diferenciação `UNAVAILABLE` x revisão negativa aprovada;
- auditoria;
- integração com safety engine da Spec 003;
- cache/PWA boundary;
- axe/Playwright da futura UI.

## Rollout

1. validar terminologia e política clínica;
2. aprovar contratos de rota/form;
3. implementar model + selector;
4. publicar UI;
5. integrar Spec 003;
6. só então remover o gate manual de alergia.
