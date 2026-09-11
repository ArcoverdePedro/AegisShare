# Contrato de Rotas — Spec 001 PEP

| Método | URL | View | Template | Permissão |
|---|---|---|---|---|
| GET | `/pacientes/` | `PatientListView` | `clinical/pep/patient_list.html` | profissional interno autorizado |
| GET/POST | `/pacientes/novo/` | `PatientCreateView` | `clinical/pep/patient_form.html` | `ADM`/`FUNC` |
| GET | `/pacientes/<id>/` | `PatientDetailView` | `clinical/pep/patient_detail.html` | acesso ao paciente |
| GET | `/pacientes/<id>/encontros/` | `EncounterListView` | `clinical/pep/encounter_list.html` | acesso ao paciente |
| GET/POST | `/pacientes/<id>/encontros/novo/` | `EncounterCreateView` | `clinical/pep/encounter_form.html` | acesso ao paciente |
| GET | `/encontros/<id>/` | `EncounterDetailView` | `clinical/pep/encounter_detail.html` | acesso ao encontro |
| GET/POST | `/encontros/<id>/evolucoes/nova/` | `ClinicalEvolutionCreateView` | `clinical/pep/evolution_form.html` | profissional interno + acesso + encontro aberto |
| GET | `/evolucoes/<id>/` | `ClinicalEvolutionDetailView` | `clinical/pep/evolution_detail.html` | acesso ao paciente do encontro |
| GET/POST | `/evolucoes/<id>/adendo/` | `ClinicalEvolutionAmendmentCreateView` | `clinical/pep/evolution_form.html` | profissional interno + acesso + encontro aberto |
| WS | `/ws/clinical/patients/<id>/` | `PatientClinicalConsumer` | atualização de UI nas telas clínicas | sessão autenticada + acesso atual ao paciente, revalidado a cada evento |
| GET/POST | `/documentos/<id>/assinar/` | `ClinicalDocumentSignView` | `clinical/pep/document_sign.html` | futuro T-PEP-08 |

## Observações

- Rotas HTTP retornam HTML server-rendered autenticado por sessão; fragmentos HTMX poderão ser introduzidos sem criar API REST pública.
- O canal WebSocket é interno, autenticado pela sessão e não constitui API REST pública.
- O canal clínico transmite somente tipo de evento, UUIDs de roteamento e data/hora; não transmite nome, CPF, diagnóstico, motivo, local ou conteúdo clínico.
- A autorização WebSocket é validada na conexão e novamente antes de cada entrega para cobrir expiração/revogação de vínculo.
- A listagem de evoluções faz parte do detalhe do encontro e preserva ordem cronológica.
- Evoluções não possuem rota de edição ou exclusão. Correções são novos registros pela rota de adendo.
- Usuário fora do escopo recebe `404` nas consultas HTTP por objeto para evitar enumeração de dados clínicos.
- A autorização é revalidada na view e nas regras de domínio/modelo; ocultar uma ação no template não concede segurança.
