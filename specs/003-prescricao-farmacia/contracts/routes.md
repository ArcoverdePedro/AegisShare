# Contrato de Rotas — Spec 003 Prescrição e Farmácia

Todas as URLs são internas, autenticadas por sessão Django e renderizadas no servidor. Nenhuma rota abaixo é API REST pública. As superfícies clínicas novas seguem a preferência FBV do `AGENTS.md`.

| Método | URL | View | Template/Resposta | Capacidade mínima |
|---|---|---|---|---|
| GET | `/prescricoes/` | `prescription_list` | `clinical/prescription/prescription_list.html` | `prescription.view_medication_request` + escopo PEP |
| GET | `/prescricoes/nova/` | `prescription_create` | `clinical/prescription/new.html` | `prescription.prescribe_medication` |
| POST | `/prescricoes/nova/` | `prescription_create` | redirect/form errors | `prescription.prescribe_medication` + escopo PEP |
| GET | `/prescricoes/<uuid:pk>/` | `prescription_detail` | `clinical/prescription/detail.html` | `prescription.view_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/submeter/` | `prescription_submit` | redirect/form errors | `prescription.prescribe_medication` + autoria/escopo PEP |
| GET | `/prescricoes/<uuid:pk>/validar/` | `prescription_validate` | `clinical/prescription/validate.html` | `prescription.validate_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/validar/` | `prescription_validate` | redirect/form errors | `prescription.validate_medication_request` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/cancelar/` | `prescription_cancel` | redirect/form errors | prescritor autor ou `prescription.cancel_medication_request` + escopo PEP |
| GET | `/prescricoes/<uuid:pk>/dispensar/` | `dispense_create` | `clinical/prescription/dispense.html` | `prescription.dispense_medication` + escopo PEP |
| POST | `/prescricoes/<uuid:pk>/dispensar/` | `dispense_create` | redirect/form errors | `prescription.dispense_medication` + escopo PEP |
| GET | `/dispensacoes/` | `dispense_list` | `clinical/prescription/dispense_list.html` | `prescription.view_medication_dispense` + escopo PEP |
| GET | `/dispensacoes/<uuid:pk>/` | `dispense_detail` | `clinical/prescription/dispense_detail.html` | `prescription.view_medication_dispense` + escopo PEP |
| GET | `/medicamentos/` | `DrugCatalogView` | `clinical/prescription/drug_catalog.html` | `prescription.view_drug` |
| GET | `/medicamentos/novo/` | `DrugCreateView` | `clinical/prescription/drug_form.html` | `prescription.manage_drug_catalog` |
| POST | `/medicamentos/novo/` | `DrugCreateView` | redirect/form errors | `prescription.manage_drug_catalog` |
| GET | `/medicamentos/<uuid:pk>/editar/` | `DrugUpdateView` | `clinical/prescription/drug_form.html` | `prescription.manage_drug_catalog` |
| POST | `/medicamentos/<uuid:pk>/editar/` | `DrugUpdateView` | redirect/form errors | `prescription.manage_drug_catalog` |
| GET | `/estoque-farmacia/` | `PharmacyStockView` | `clinical/prescription/pharmacy_stock.html` | `prescription.view_pharmacy_stock` |

## Regras HTTP

- toda mutação usa `POST` + CSRF; GET nunca altera estado;
- prescrição/dispensação fora do escopo PEP retorna 404 quando a existência do registro puder revelar PHI;
- todas as superfícies GET RX respondem `Cache-Control: private, no-store, max-age=0` e variam por sessão/HTMX;
- prescrições submetidas não expõem rota genérica de edição de conteúdo;
- validação e dispensação chamam services que revalidam estado, autorização e referências dentro da transação;
- conflito de estoque/estado retorna mensagem segura sem detalhes de banco;
- nenhuma rota usa prefixo `/api/`.

## Edição de catálogo

`DrugUpdateView` só permite editar atributos administrativos/catalográficos autorizados. Se uma mudança puder alterar interpretação clínica histórica, deve haver versionamento/desativação em vez de reescrita silenciosa. `Interaction` e `DoseRule` permanecem governados por services/modelos e conteúdo real continua bloqueado até T-RX-02.

## PWA

Os POSTs de criação/submissão/cancelamento de prescrição, validação farmacêutica, dispensação e manutenção de catálogo/estoque permanecem `network-only`. O service worker não enfileira essas URLs e as páginas RX não entram em Cache Storage/IndexedDB clínico.
