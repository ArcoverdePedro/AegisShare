RX_GET_SURFACE_NAMES = frozenset(
    {
        "prescription_list",
        "prescription_create",
        "prescription_detail",
        "prescription_validate",
        "dispense_create",
        "dispense_list",
        "dispense_detail",
        "drug_catalog",
        "drug_create",
        "drug_update",
        "pharmacy_stock",
    }
)

# Rotas RX sem GET devem ser adicionadas explicitamente aqui. Isso evita que o gate
# de Cache-Control force uma chamada GET em uma superfície POST-only.
RX_NON_GET_SURFACE_NAMES = frozenset(
    {
        "prescription_submit",
        "prescription_cancel",
    }
)

RX_REVIEWED_SURFACE_NAMES = RX_GET_SURFACE_NAMES | RX_NON_GET_SURFACE_NAMES
