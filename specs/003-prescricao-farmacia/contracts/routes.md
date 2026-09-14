# Contrato de Rotas — Spec 003 Prescrição e Farmácia

Todas as URLs são internas, autenticadas por sessão Django e renderizadas no servidor. Nenhuma rota abaixo é API REST pública.

| Método | URL | View prevista | Template/Resposta | Capacidade mínima |
|---|---|---|---|---|
| GET | `/prescricoes/` | `MedicationRequestListView` | `clinical/prescription/prescription_list.html` | `prescription.view_medication_request` + escopo PEP |
| GET | `/prescricoes/nova/` | `MedicationRequestCreateView` | `clinical/prescription/new.html` | `prescription.prescribe_medication` |
| POST | `/prescricoes/nova/` | `MedicationRequestCreateView` | redirect/form errors | `prescription.prescribe_medication` + escopo PEP |
| GET | `/prescricoes/<uuid:pk>/` | `MedicationRequestDetailView` | `clinical/prescription/detail.html` | `prescription.view_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/submeter/` | `MedicationRequestSubmitView` | redirect/form errors | `prescription.prescribe_medication` + autoria/escopo PEP |
| GET | `/prescricoes/<uuid:pk>/validar/` | `MedicationRequestValidateView` | `clinical/prescription/validate.html` | `prescription.validate_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/validar/` | `MedicationRequestValidateView` | redirect/form errors | `prescription.validate_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/cancelar/` | `MedicationRequestCancelView` | redirect/form errors | prescritor autor ou capacidade clínica específica + escopo PEP |
| GET | `/prescricoes/<uuid:pk>/dispensar/` | `MedicationDispenseCreateView` | `clinical/prescription/dispense.html` | `prescription.dispense_medication` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/dispensar/` | `MedicationDispenseCreateView` | redirect/form errors | `prescription.dispense_medication` + escopo PEP |
| GET | `/dispensacoes/` | `MedicationDispenseListView` | `clinical/prescription/dispense_list.html` | `prescription.view_medication_dispense` + escopo PEP |
| GET | `/dispensacoes/<uuid:pk>/` | `MedicationDispenseDetailView` | `clinical/prescription/dispense_detail.html` | `prescription.view_medication_dispense` + escopo PEP |
| GET | `/medicamentos/` | `DrugCatalogView` | `clinical/prescription/drug_catalog.html` | `prescription.view_drug` |
| GET | `/medicamentos/novo/` | `DrugCreateView` | `clinical/prescription/drug_form.html` | `prescription.manage_drug_catalog` |
| POST | `/medicamentos/novo/` | `DrugCreateView` | redirect/form errors | `prescription.manage_drug_catalog` |
| GET | `/medicamentos/<uuid:pk>/editar/` | `DrugUpdateView` | `clinical/prescription/drug_form.html` | `prescription.manage_drug_catalog` |
| POST | `/medicamentos/<uuid:pk>/editar/` | `DrugUpdateView` | redirect/form errors | `prescription.manage_drug_catalog` |
| GET | `/estoque-farmacia/` | `PharmacyStockView` | `clinical/prescription/pharmacy_stock.html` | `prescription.view_pharmacy_stock` |

## Regras HTTP

- toda mutação usa `POST` + CSRF; GET nunca altera estado;
- prescrição/dispensação fora do escopo PEP retorna 404 quando a existência do registro puder revelar PHI;
- lista e detalhes clínicos usam `Cache-Control: private, no-store, max-age=0`;
- prescrições submetidas não expõem rota genérica de edição de conteúdo;
- validação e dispensação chamam services que revalidam estado, autorização e referências dentro da transação;
- conflito de estoque/estado retorna mensagem segura sem detalhes de banco;
- nenhuma rota usa prefixo `/api/`.

## Edição de catálogo

`DrugUpdateView` só permite editar atributos administrativos/catalográficos autorizados. Se uma mudança puder alterar interpretação clínica histórica, deve haver versionamento/desativação em vez de reescrita silenciosa. `Interaction` e `DoseRule` terão manutenção administrativa controlada em incremento próprio ou Django Admin restrito até que telas específicas sejam aprovadas; não devem receber endpoints JSON públicos.

## PWA

Os POSTs de:

- criação/submissão/cancelamento de prescrição;
- validação farmacêutica;
- dispensação;
- manutenção de catálogo/estoque

permanecem `network-only`. O service worker não deve enfileirar essas URLs, e a fila IndexedDB não deve ser carregada automaticamente nessas telas.
