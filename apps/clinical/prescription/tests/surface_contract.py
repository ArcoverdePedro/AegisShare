RX_GET_SURFACE_NAMES = frozenset(
    {
        "drug_catalog",
        "drug_create",
        "drug_update",
        "pharmacy_stock",
    }
)

# Rotas RX sem GET devem ser adicionadas explicitamente aqui. Isso evita que o gate
# de Cache-Control force uma chamada GET em uma futura superfície POST-only.
RX_NON_GET_SURFACE_NAMES = frozenset()

RX_REVIEWED_SURFACE_NAMES = RX_GET_SURFACE_NAMES | RX_NON_GET_SURFACE_NAMES
