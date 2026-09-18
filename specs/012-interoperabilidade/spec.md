# Spec 012 — Interoperabilidade por arquivos

## Status

**Aprovada pelo mantenedor em 2026-09-16**, pela instrução “aprovado, continue”. Implementação do recorte v1 autorizada; uso com dados reais continua sujeito à política institucional de transferência e guarda.

## Contexto

O Core, PEP, ADT, Prescrição/Farmácia, Enfermagem e PWA possuem recortes implementados. As tarefas abertas de assinatura, referências farmacêuticas e exceções de administração dependem de governança externa. Não serão desbloqueadas por esta spec.

A Spec 012, prevista como P0 no SDD v3, foi iniciada neste incremento para exportar o cadastro mínimo de **um paciente por operação**, em arquivo FHIR R4 JSON, pela interface autenticada. Isso estabelece a fronteira de intercâmbio sem duplicar o PEP. Não conclui a interoperabilidade necessária ao LIS: ingestão HL7/ASTM e mapeamento de resultados exigem extensão aprovada antes dos resultados do módulo 005; pedidos e coleta manual já estão implementados na v1 LIS.

## User Stories

- Como profissional interno autorizado, quero baixar o cadastro mínimo de um paciente acessível para intercâmbio por arquivo.
- Como responsável pela auditoria, quero identificar quem gerou cada arquivo e quando, sem copiar seu conteúdo para logs.

## Requisitos Funcionais

- **RF-INT-01:** oferecer formulário server-rendered de seleção de paciente e confirmação explícita; GET nunca produz exportação.
- **RF-INT-02:** exigir sessão, profissional interno, capacidade `interoperability.export_patient` e escopo atual de `accessible_patients(user)` em GET e POST. Ser administrador do PEP não substitui a capacidade; aplicam-se as regras nativas de superusuário do Django.
- **RF-INT-03:** gerar um recurso `Patient` conforme a allowlist de `contracts/fhir-patient.md`, serializado em UTF-8 como attachment. Nenhuma busca FHIR, API REST, token Bearer ou URL pública de download.
- **RF-INT-04:** persistir recibo append-only de geração com ator, paciente, horário, versão do contrato e SHA-256 dos bytes; registrar acesso e geração sem payload identificável nos logs. O recibo significa arquivo gerado, não comprovação de entrega ao destinatário.
- **RF-INT-05:** negar paciente inativo, vínculo expirado/revogado e IDs fora do queryset; validação e mensagens não devem revelar existência de paciente fora do escopo.
- **RF-INT-06:** manter formulário, erros e attachment `private, no-store`; nenhuma fila offline, cache clínico, push ou armazenamento de arquivo no servidor.

## Requisitos Não Funcionais

- **RNF-INT-01:** FBV, Django Forms, ORM, `json` e `hashlib` da stdlib; reaproveitar sessão, CSRF, autorização PEP e auditlog.
- **RNF-INT-02:** interface responsiva, navegação por teclado, labels/erros acessíveis; axe sem violações sérias/críticas.
- **RNF-INT-03:** um único paciente por POST; sem N+1, exportação em lote, jobs ou dependência nova no recorte inicial.
- **RNF-INT-04:** falha na persistência do recibo/auditoria impede entrega do arquivo; mensagens de erro não expõem traceback nem dados do paciente.

## Critérios de Aceitação

Os cenários CA-INT-01 a CA-INT-06 estão em [features/patient-export.feature](features/patient-export.feature). Os cenários estão vinculados aos testes Django/Playwright na matriz abaixo; não há runner pytest-bdd adicional.

## Telas e Fluxos

`GET /interop/exportar/` → `interop/export_form.html` → seleção/confirmar → `POST` na mesma rota → attachment ou formulário com erros. A página usa o layout existente. Link de navegação condicionado à capacidade, com autorização efetiva no servidor.

## Fora de Escopo

Importação, HL7/ASTM, DICOM, XML, TISS, Bundle, laudos, prescrições, exportação de CPF/contatos, assinatura, consentimento jurídico automatizado, envio a terceiros, logs consultáveis em nova UI, Celery/outbox e cache offline. Nenhuma tabela genérica `FHIRResource` nem cadastro paralelo de paciente.

## Dependências

Specs 000 (sessão/auditoria), 001 (paciente/escopo) e 014 (fronteiras de cache). O recorte de solicitações do titular da Spec 013 está implementado; aprovação técnica desta spec não estabelece base legal ou política institucional para transferência de dados reais.

## Riscos

- Download contém nome e nascimento: `no-store` protege caches HTTP, mas não apaga o arquivo salvo pelo usuário. A UI informa isso antes da confirmação; uso real exige política institucional de destinatário e guarda.
- `Patient.sex` não possui semântica formal de gênero administrativo: não converter automaticamente para `gender`.
- UUID exportado é identidade técnica desta instalação; não constitui identificador nacional nem permite reconciliar pacientes entre instituições por si só.
- Recibo não preserva payload: hash comprova correspondência com um arquivo apresentado, mas não permite reconstruir cadastro histórico.

## Rastreabilidade

Testes Django: `apps/interoperability/tests/test_export.py` (`PatientExportTests`).
Jornadas de navegador: `tests/e2e/interop_journeys.spec.js`, preparadas por `prepare_interop_journeys.py` e incluídas na CI.

| Requisitos | Rota/View | Template/saída | Aceitação | Testes implementados |
|---|---|---|---|---|
| RF-INT-01; RNF-INT-02 | `/interop/exportar/` / `patient_export` | `interop/export_form.html` | CA-INT-01/03 | `test_get_does_not_export_and_options_are_scoped`; `test_missing_confirmation_and_empty_post_are_bound_errors`; Playwright telefone/tablet + axe |
| RF-INT-02/05 | mesma FBV + queryset PEP | formulário/403/login | CA-INT-02/03 | `test_grant_revoked_or_expired_between_get_and_post`; `test_permission_revoked_between_get_and_post`; `test_unknown_and_out_of_scope_have_same_errors`; `test_csrf_required_and_rejection_is_private`; Playwright CA-INT-02/03 |
| RF-INT-03; RNF-INT-01/03 | mesma FBV | attachment JSON | CA-INT-01/04 | `test_export_allowlist_utf8_and_audited_receipt`; Playwright CA-INT-01/04; gate arquitetural existente |
| RF-INT-04; RNF-INT-04 | mesma FBV + transação | recibo/auditlog | CA-INT-01/05 | `test_access_audit_failure_rolls_back_receipt_and_create_audit`; `test_receipt_audit_failure_prevents_download`; `test_receipt_immutable_and_patient_protected` |
| RF-INT-06 | FBV + `PrivateWorkflowMiddleware` | no-store/fallback | CA-INT-06 | asserções de privacidade nos testes HTTP; Playwright CA-INT-06 |

## Definition of Done

- [x] Proposta, plano, tarefas, contratos e aceitação escritos.
- [x] Aprovação explícita registrada pelo mantenedor.
- [x] Implementação e migration reversível, aplicada/revertida/reaplicada em banco descartável.
- [x] Testes de comportamento, autorização, auditoria e mapeamento.
- [x] Cenários vinculados a Django/Playwright; mobile e axe.
- [x] Gates locais executados e resultados registrados em `validation.md`.
- [ ] CI remota com PostgreSQL/Redis e gates institucionais de compliance; validação local não equivale a certificação.
- [x] Documentação operacional e rastreabilidade atualizadas com testes reais.

## Próxima extensão

[Recebimento laboratorial cifrado em quarentena](extensions/lab-inbox/spec.md): extensão aprovada e implementada em 2026-09-18; [evidências](extensions/lab-inbox/validation.md). Não altera o contrato de exportação nem implementa parsing HL7/ASTM.
