# Rotas — Spec 012 v1 (v1 aprovada)

Namespace: `interoperability`. Nome: `patient_export`. Rota implementada em `apps/interoperability/urls.py`.

| Método | URL | FBV | Template/saída | Permissão |
|---|---|---|---|---|
| GET | `/interop/exportar/` | `patient_export` | `interop/export_form.html` | sessão + profissional interno + `interoperability.export_patient`; opções limitadas ao PEP |
| POST | `/interop/exportar/` | `patient_export` | attachment ou mesmo formulário com erros | mesmas regras + CSRF + confirmação + escopo atual do paciente |

Outros métodos: 405 para usuário autenticado. Nenhum arquivo em GET, token de download ou URL de recurso FHIR. Respostas sensíveis: `Cache-Control: private, no-store` e `Vary: Cookie`. Não usar HTMX/fetch para submissão.

Attachment: `Content-Type: application/fhir+json`, `Content-Disposition: attachment; filename="patient-export-<receipt_uuid>.json"`, `X-Content-Type-Options: nosniff`. Nome do arquivo não contém nome/CPF do paciente.
