# Modelo implementado — preparação de contas

App apps.admin.billing, label billing. Duas tabelas implementadas na migration billing.0001_initial.

| Modelo | Campos |
|---|---|
| HospitalAccount | id UUID; encounter OneToOne pep.Encounter PROTECT; opened_by FK User PROTECT; opened_at auto_now_add; operation_key UUID com UniqueConstraint uniq_billing_account_operation |
| BillingItem | id UUID; account FK HospitalAccount PROTECT, related_name items; description CharField(200); quantity PositiveIntegerField; unit_price DecimalField(12,2); recorded_by FK User PROTECT; recorded_at auto_now_add; operation_key UUID com UniqueConstraint uniq_billing_item_operation |

Checks: 1 ≤ quantity ≤ 999999; 0 ≤ unit_price ≤ 9999999999.99. Forms/domain rejeitam valores não finitos, casas excessivas e quantidades fracionárias; descrição trim externo/não vazia. Preços 1 e 1.00 são equivalentes para retry. Descrição preserva espaços internos/case.

BRL é constante do recorte, sem campo de múltiplas moedas inexistentes. Subtotal derivado com Decimal; total agregado no ORM com precisão suficiente, sem float nem totais armazenados. Maior subtotal individual tem 16 dígitos inteiros e duas casas. Não somar somente a página.

Contas: ordering -opened_at/-id, índice billing_account_opened_idx. Itens: -recorded_at/-id, índice account/-recorded_at/-id chamado billing_item_account_idx. Paciente por encounter.patient; sem Patient/Admission/Insurance duplicados.

Capacidades em HospitalAccount: billing.view_accounts/open_account/add_item, sem grants automáticos. Sem Admin de contas/itens; registros imutáveis nas entradas. __str__ só tipo/UUID. Auditlog de item exclui description/quantity/unit_price; nenhum nome/total em object_repr/additional_data.
