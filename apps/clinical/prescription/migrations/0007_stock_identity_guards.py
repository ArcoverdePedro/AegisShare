from django.db import migrations

STOCK_ITEM_FUNCTION = "rx_guard_stock_item_identity"
STOCK_ITEM_TRIGGER = "rx_stock_item_identity_guard"
LOT_FUNCTION = "rx_guard_lot_identity"
LOT_TRIGGER = "rx_lot_identity_guard"


def create_stock_identity_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    stock_item = apps.get_model("prescription", "StockItem")
    lot = apps.get_model("prescription", "Lot")
    movement = apps.get_model("prescription", "StockMovement")

    stock_table = quote(stock_item._meta.db_table)
    lot_table = quote(lot._meta.db_table)
    movement_table = quote(movement._meta.db_table)
    stock_function = quote(STOCK_ITEM_FUNCTION)
    lot_function = quote(LOT_FUNCTION)

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {stock_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM {lot_table}
                 WHERE stock_item_id = OLD.id
            ) AND (
                NEW.drug_id IS DISTINCT FROM OLD.drug_id
                OR NEW.storage_location IS DISTINCT FROM OLD.storage_location
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Estoque com lotes não pode ter medicamento ou localização reescritos.';
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(STOCK_ITEM_TRIGGER)}
        BEFORE UPDATE ON {stock_table}
        FOR EACH ROW
        EXECUTE FUNCTION {stock_function}();
        """
    )

    schema_editor.execute(
        f"""
        CREATE OR REPLACE FUNCTION {lot_function}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM {movement_table}
                 WHERE lot_id = OLD.id
            ) AND (
                NEW.stock_item_id IS DISTINCT FROM OLD.stock_item_id
                OR NEW.lot_number IS DISTINCT FROM OLD.lot_number
                OR NEW.expires_on IS DISTINCT FROM OLD.expires_on
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Lote com movimentação não pode ter sua identidade histórica reescrita.';
            END IF;

            RETURN NEW;
        END;
        $function$;
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {quote(LOT_TRIGGER)}
        BEFORE UPDATE ON {lot_table}
        FOR EACH ROW
        EXECUTE FUNCTION {lot_function}();
        """
    )


def drop_stock_identity_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    stock_item = apps.get_model("prescription", "StockItem")
    lot = apps.get_model("prescription", "Lot")

    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(STOCK_ITEM_TRIGGER)} ON {quote(stock_item._meta.db_table)};"
    )
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(STOCK_ITEM_FUNCTION)}();")
    schema_editor.execute(
        f"DROP TRIGGER IF EXISTS {quote(LOT_TRIGGER)} ON {quote(lot._meta.db_table)};"
    )
    schema_editor.execute(f"DROP FUNCTION IF EXISTS {quote(LOT_FUNCTION)}();")


class Migration(migrations.Migration):
    dependencies = [
        ("prescription", "0006_used_drug_integrity"),
    ]

    operations = [
        migrations.RunPython(create_stock_identity_guards, drop_stock_identity_guards),
    ]
