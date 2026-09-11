# Contrato de Rotas — Spec 001 PEP

| Método | URL | View planejada | Template | Permissão |
|---|---|---|---|---|
| GET | `/pacientes/` | `PatientListView` | `clinical/pep/patient_list.html` | profissional autorizado |
| GET/POST | `/pacientes/novo/` | `PatientCreateView` | `clinical/pep/patient_form.html` | staff/médico autorizado |
| GET | `/pacientes/<id>/` | `PatientDetailView` | `clinical/pep/patient_detail.html` | acesso ao paciente |
| GET | `/pacientes/<id>/encontros/` | `PatientEncounterListView` | parcial/lista de encontros | acesso ao paciente |
| GET | `/encontros/<id>/` | `EncounterDetailView` | `clinical/pep/encounter_detail.html` | acesso ao encontro |
| GET/POST | `/encontros/<id>/evolucoes/nova/` | `EvolutionCreateView` | `clinical/pep/evolution_form.html` | papel clínico autorizado |
| GET | `/encontros/<id>/evolucoes/` | `EvolutionListView` | parcial de evoluções | acesso ao encontro |
| GET/POST | `/documentos/<id>/assinar/` | `ClinicalDocumentSignView` | `clinical/pep/document_sign.html` | signatário autorizado |

## Observações

- Rotas retornam HTML completo ou fragmentos HTMX autenticados por sessão.
- Não haverá endpoints REST públicos.
- A autorização deve ser revalidada na view e no serviço de domínio, não apenas no template.