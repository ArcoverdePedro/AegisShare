# Plano Técnico — Spec 001 PEP

## Arquitetura

Criar bounded context clínico `apps/clinical/pep` dentro do monólito. O módulo usa serviços internos do Core para identidade, autorização, auditoria, documentos e notificações.

## Modelo de Dados

Modelos planejados: `Patient`, `Encounter`, `Observation`, `Condition`, `AllergyIntolerance`, `ClinicalEvolution`, `DocumentReference`, `Consent` e relações com usuário/profissional. A modelagem final será detalhada em `data-model.md` antes das migrations.

## Rotas e Views

Contratos em `contracts/routes.md`. As views serão server-rendered e HTMX para parciais. Nenhum endpoint REST público será criado.

## Formulários e Validação

Contratos em `contracts/forms.md`. Validações críticas incluem identificadores do paciente, data de nascimento, campos obrigatórios por tipo de registro, autorização por papel/objeto e imutabilidade após assinatura.

## Templates e Componentes HTMX

- listagem/pesquisa de pacientes;
- resumo longitudinal;
- cartões de alergias/condições/observações;
- formulário de evolução;
- histórico do encontro;
- diálogo/tela de assinatura.

## Eventos Internos

Planejados: `patient.created`, `encounter.opened`, `observation.recorded`, `clinical.evolution.created`, `document.signed`. Eventos clínicos não devem carregar mais dados pessoais que o necessário.

## PWA

Consulta móvel é prevista; offline de dados clínicos só será habilitado conforme política da Spec 014. Formulários offline críticos entram em specs específicas, não automaticamente no PEP inteiro.

## Segurança e LGPD

- deny-by-default;
- RBAC + ABAC por papel, setor/vínculo e objeto;
- auditoria de leitura e escrita;
- consentimento quando aplicável;
- evitar PHI em logs, notificações e caches;
- timeout de sessão e MFA herdados do Core.

## Migrações

Somente após `data-model.md` e aprovação desta spec. Cada migration deve ter rollback lógico/documentado.

## Testes

- unitários de modelos e regras de domínio;
- views e autorização por objeto;
- Gherkin para evolução e acesso negado;
- E2E para cadastro, busca, abertura do prontuário e evolução;
- axe-core nos templates principais;
- testes de auditoria e vazamento de dados.

## Rollout

1. Aprovar Spec 001.
2. Fechar modelo de dados e contratos.
3. Criar migrations e app vazio.
4. Implementar Patient e autorização.
5. Implementar Encounter e evolução.
6. Integrar auditoria/assinatura/notificação.
7. Validar PWA e acessibilidade.
8. Liberar por feature flag interna/setor piloto.